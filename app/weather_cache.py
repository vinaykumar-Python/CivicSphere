import asyncio
import logging
import math
import time
from typing import Any

import httpx

logger = logging.getLogger("civiccare.weather")

FRESH_CACHE_SECONDS = 300
MAX_STALE_SECONDS = 6 * 60 * 60

_cache: dict[str, dict[str, Any]] = {}
_cache_lock = asyncio.Lock()


def _cache_key(url: str, params: dict[str, Any]) -> str:
    return f"{url}?{httpx.QueryParams(params)}"


def _safe_number(value: Any, field: str) -> float:
    if value is None:
        raise ValueError(f"Backup weather data is missing {field}.")

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid backup weather measurement: {field}.") from exc

    if not math.isfinite(result):
        raise ValueError(f"Invalid backup weather measurement: {field}.")

    return result


def _wttr_to_open_meteo(
    payload: dict[str, Any],
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    """Convert wttr.in JSON into the format used by the weather routes."""

    current_list = payload.get("current_condition") or []

    if not current_list or not isinstance(current_list[0], dict):
        raise ValueError("Backup provider returned no current conditions.")

    item = current_list[0]

    temperature = _safe_number(item.get("temp_C"), "temperature")
    feels_like = (
        _safe_number(item.get("FeelsLikeC"), "feels-like temperature")
        if item.get("FeelsLikeC") is not None
        else temperature
    )
    precipitation = _safe_number(item.get("precipMM"), "precipitation")
    wind = _safe_number(item.get("windspeedKmph"), "wind speed")
    humidity = _safe_number(item.get("humidity"), "humidity")

    if not 0 <= humidity <= 100:
        raise ValueError("Backup provider returned invalid humidity.")

    if wind < 0 or precipitation < 0:
        raise ValueError("Backup provider returned invalid weather measurements.")

    weather_desc = item.get("weatherDesc") or [{}]

    description = (
        str(weather_desc[0].get("value", "Unknown conditions"))
        if isinstance(weather_desc[0], dict)
        else "Unknown conditions"
    )

    desc = description.lower()

    if "thunder" in desc:
        code = 95
    elif "snow" in desc or "sleet" in desc or "ice" in desc:
        code = 71
    elif "heavy rain" in desc:
        code = 65
    elif "rain" in desc or "drizzle" in desc:
        code = 61
    elif "fog" in desc or "mist" in desc:
        code = 45
    elif "cloud" in desc or "overcast" in desc:
        code = 3
    elif "clear" in desc or "sunny" in desc:
        code = 0
    else:
        code = 2

    hourly_values = []

    for day in payload.get("weather") or []:
        for hour in day.get("hourly") or []:
            if isinstance(hour, dict) and hour.get("precipMM") is not None:
                hourly_values.append(
                    _safe_number(hour["precipMM"], "hourly precipitation")
                )

    return {
        "current": {
            "temperature_2m": temperature,
            "apparent_temperature": feels_like,
            "relative_humidity_2m": humidity,
            "is_day": 1 if item.get("isdaytime") == "yes" else 0,
            "time": item.get("localObsDateTime"),
            "precipitation": precipitation,
            "rain": precipitation,
            "wind_speed_10m": wind,
            "weather_code": code,
        },
        "current_units": {
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "rain": "mm",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "precipitation": hourly_values[:6],
        },
        "backup_description": description,
        "backup_provider": "wttr.in",
        "backup_coordinates": {
            "latitude": latitude,
            "longitude": longitude,
        },
    }


async def _request_open_meteo(
    url: str,
    params: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Open-Meteo returned unexpected JSON.")

    if data.get("error"):
        raise ValueError("Open-Meteo returned a weather API error.")

    return data


async def _request_backup(
    params: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:

    latitude = float(params["latitude"])
    longitude = float(params["longitude"])

    backup_url = (
        "https://wttr.in/"
        f"{latitude:.4f},{longitude:.4f}"
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": "CivicCareAI/1.0"},
    ) as client:
        response = await client.get(
            backup_url,
            params={"format": "j1"},
        )
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Backup weather service returned unexpected JSON.")

    return _wttr_to_open_meteo(payload, latitude, longitude)


async def get_json_cached(
    url: str,
    params: dict[str, Any],
    *,
    timeout: float = 20.0,
) -> tuple[dict[str, Any], bool]:
    """
    Prefer Open-Meteo, then backup weather provider, then recent cached data.

    Returns (weather_data, using_cached_data).
    """

    key = _cache_key(url, params)
    now = time.time()

    async with _cache_lock:
        cached = _cache.get(key)

        if cached and now - cached["saved_at"] <= FRESH_CACHE_SECONDS:
            return cached["data"], False

    last_error: Exception | None = None

    # Primary weather provider.
    for attempt in range(2):
        try:
            data = await _request_open_meteo(url, params, timeout)

            async with _cache_lock:
                _cache[key] = {
                    "data": data,
                    "saved_at": time.time(),
                }

            return data, False

        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc

            if attempt == 0:
                await asyncio.sleep(1)

    # Backup provider for forecast requests.
    if url.endswith("/forecast"):
        try:
            data = await _request_backup(params, timeout)

            async with _cache_lock:
                _cache[key] = {
                    "data": data,
                    "saved_at": time.time(),
                }

            logger.warning("Weather data retrieved from backup provider.")
            return data, False

        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            last_error = exc
            logger.warning("Backup weather provider failed: %s", exc)

    # Recent cached data as last resort.
    async with _cache_lock:
        cached = _cache.get(key)

        if cached and time.time() - cached["saved_at"] <= MAX_STALE_SECONDS:
            age = int(time.time() - cached["saved_at"])
            logger.warning("Using cached weather data. Age: %s seconds.", age)

            return cached["data"], True

    logger.error("No live or cached weather data available: %s", last_error)

    raise RuntimeError(
        "Weather providers are temporarily unavailable, "
        "and no recent cached data is available."
    ) from last_error