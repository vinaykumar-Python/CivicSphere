from fastapi import APIRouter, HTTPException, Query

from app.weather_cache import get_json_cached

router = APIRouter(prefix="/api/weather", tags=["Weather"])

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@router.get("/current")
async def get_current_weather(
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
                detail="City not found. Try another city name.",
            )

        location = results[0]
        latitude = location["latitude"]
        longitude = location["longitude"]

    try:
        weather_data, using_cached_data = await get_json_cached(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "is_day,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    current = weather_data.get("current")

    if not current:
        raise HTTPException(
            status_code=502,
            detail="Weather information is currently unavailable.",
        )

    source = weather_data.get("backup_provider", "Open-Meteo")

    return {
        "location": {
            "name": location.get("name") if location else "Selected location",
            "admin1": location.get("admin1") if location else None,
            "country": location.get("country") if location else None,
            "latitude": latitude,
            "longitude": longitude,
        },
        "current": current,
        "units": weather_data.get("current_units", {}),
        "backup_description": weather_data.get("backup_description"),
        "observed_at": (
            current.get("time")
            or current.get("localObsDateTime")
        ),
        "timezone": weather_data.get("timezone"),
        "timezone_abbreviation": weather_data.get("timezone_abbreviation"),
        "source": source,
        "using_cached_data": using_cached_data,
    }
