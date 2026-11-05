from fastapi import APIRouter, HTTPException, Query

from app.weather_cache import get_json_cached

router = APIRouter(prefix="/api/risk", tags=["Civic Risk Intelligence"])

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def classify_risk(
    value: float,
    thresholds: list[tuple[float, str, str]],
) -> dict:
    """Return the highest applicable illustrative risk threshold."""
    for limit, level, message in thresholds:
        if value >= limit:
            return {
                "level": level,
                "message": message,
                "threshold": limit,
            }

    return {
        "level": "Low",
        "message": "No elevated risk identified by this indicator.",
        "threshold": None,
    }


@router.get("/weather")
async def assess_weather_risk(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    city: str | None = Query(default=None, min_length=2, max_length=100),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=400,
            detail="Provide both latitude and longitude.",
        )

    if latitude is None and not city:
        raise HTTPException(
            status_code=400,
            detail="Provide coordinates or a city name.",
        )

    location = None

    if city:
        try:
            geo_data, _ = await get_json_cached(
                GEOCODING_URL,
                {
                    "name": city,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                },
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=502,
                detail=str(exc),
            ) from exc

        results = geo_data.get("results") or []

        if not results:
            raise HTTPException(
                status_code=404,
                detail="City not found. Check the spelling.",
            )

        location = results[0]
        latitude = location["latitude"]
        longitude = location["longitude"]

    try:
        data, using_cached_data = await get_json_cached(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "rain,"
                    "wind_speed_10m,"
                    "weather_code"
                ),
                "hourly": "precipitation",
                "forecast_hours": 6,
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    current = data.get("current")

    if not current:
        raise HTTPException(
            status_code=502,
            detail="Weather risk data is currently unavailable.",
        )

    temperature_value = current.get("temperature_2m")
    apparent_value = current.get("apparent_temperature")
    rain_value = current.get("rain")
    precipitation_value = current.get("precipitation")
    wind_value = current.get("wind_speed_10m")

    # Missing measurements must not be silently interpreted as zero.
    required_values = {
        "temperature_2m": temperature_value,
        "wind_speed_10m": wind_value,
        "precipitation": precipitation_value,
    }

    missing_values = [
        name for name, value in required_values.items() if value is None
    ]

    if missing_values:
        raise HTTPException(
            status_code=502,
            detail=(
                "Weather data is incomplete. Missing measurements: "
                + ", ".join(missing_values)
            ),
        )

    temperature = float(temperature_value)
    feels_like = float(
        apparent_value if apparent_value is not None else temperature
    )
    rain = float(rain_value) if rain_value is not None else 0.0
    precipitation = float(precipitation_value)
    wind = float(wind_value)

    # These are illustrative project screening thresholds, not official warnings.
    heat = classify_risk(
        feels_like,
        [
            (
                45,
                "Severe",
                "Extreme apparent temperature. Consider heat-safety precautions.",
            ),
            (
                40,
                "High",
                "Very high apparent temperature. Heat stress is possible.",
            ),
            (
                35,
                "Moderate",
                "Elevated apparent temperature. Stay hydrated.",
            ),
        ],
    )

    wind_risk = classify_risk(
        wind,
        [
            (
                75,
                "Severe",
                "Very strong winds. Check official weather warnings.",
            ),
            (
                50,
                "High",
                "Strong winds may create hazards.",
            ),
            (
                30,
                "Moderate",
                "Increased wind speeds. Use caution outdoors.",
            ),
        ],
    )

    rainfall_risk = classify_risk(
        precipitation,
        [
            (
                50,
                "Severe",
                "Very high current precipitation. Check official alerts.",
            ),
            (
                20,
                "High",
                "Heavy current precipitation may cause local disruption.",
            ),
            (
                7.5,
                "Moderate",
                "Elevated precipitation. Monitor local conditions.",
            ),
        ],
    )

    risks = [
        {"type": "Heat", **heat},
        {"type": "Wind", **wind_risk},
        {"type": "Rainfall", **rainfall_risk},
    ]

    order = {
        "Low": 0,
        "Moderate": 1,
        "High": 2,
        "Severe": 3,
    }

    overall = max(
        risks,
        key=lambda item: order[item["level"]],
    )["level"]

    hourly = data.get("hourly") or {}
    hourly_precipitation = hourly.get("precipitation") or []

    next_six_hour_precipitation = sum(
        float(value)
        for value in hourly_precipitation[:6]
        if value is not None
    )

    if next_six_hour_precipitation >= 50:
        forecast_note = (
            "High accumulated precipitation is indicated for the "
            "available next-six-hour forecast."
        )
    elif next_six_hour_precipitation >= 20:
        forecast_note = (
            "Elevated accumulated precipitation is indicated for the "
            "available next-six-hour forecast."
        )
    else:
        forecast_note = (
            "The available next-six-hour forecast does not cross this "
            "project's elevated precipitation threshold."
        )

    return {
        "location": {
            "name": location.get("name") if location else "Selected location",
            "admin1": location.get("admin1") if location else None,
            "country": location.get("country") if location else None,
            "latitude": latitude,
            "longitude": longitude,
        },
        "overall_risk": overall,
        "indicators": {
            "temperature_c": temperature,
            "apparent_temperature_c": feels_like,
            "current_precipitation_mm": precipitation,
            "current_rain_mm": rain,
            "wind_speed_kmh": wind,
            "next_six_hour_precipitation_mm": round(
                next_six_hour_precipitation,
                2,
            ),
        },
        "risks": risks,
        "forecast_note": forecast_note,
        "notice": (
            "These are project screening indicators, not official weather "
            "warnings or confirmation of flooding, damage, or other incidents. "
            "Thresholds are illustrative and should be validated before "
            "operational use."
        ),
        "source": data.get("backup_provider", "Open-Meteo"),
        "observed_at": (
            current.get("time")
            or current.get("localObsDateTime")
        ),
        "timezone": data.get("timezone"),
        "timezone_abbreviation": data.get("timezone_abbreviation"),
        "using_cached_data": using_cached_data,
    }
