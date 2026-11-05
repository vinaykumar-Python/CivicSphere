import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.weather_cache import get_json_cached


@pytest.fixture
def client():
    return TestClient(app)


def test_weather_requires_location(client):
    response = client.get("/api/weather/current")

    assert response.status_code == 400


def test_weather_rejects_only_one_coordinate(client):
    response = client.get(
        "/api/weather/current?latitude=12.97"
    )

    assert response.status_code == 400


def test_risk_requires_location(client):
    response = client.get("/api/risk/weather")

    assert response.status_code == 400


def test_risk_rejects_only_one_coordinate(client):
    response = client.get(
        "/api/risk/weather?longitude=77.59"
    )

    assert response.status_code == 400


def test_weather_rejects_invalid_coordinates(client):
    response = client.get(
        "/api/weather/current?latitude=120&longitude=77"
    )

    assert response.status_code == 422


def test_risk_rejects_invalid_coordinates(client):
    response = client.get(
        "/api/risk/weather?latitude=12&longitude=200"
    )

    assert response.status_code == 422


def test_current_weather_reports_observation_and_backup_source(
    client,
    monkeypatch,
):
    import app.weather_routes as weather_routes

    async def cached_weather(url, params):
        if "geocoding-api" in url:
            return {
                "results": [
                    {
                        "name": "Bengaluru",
                        "admin1": "Karnataka",
                        "country": "India",
                        "latitude": 12.97,
                        "longitude": 77.59,
                    }
                ]
            }, False

        return {
            "current": {
                "temperature_2m": 27.5,
                "apparent_temperature": 29.0,
                "relative_humidity_2m": 70,
                "is_day": 1,
                "precipitation": 0.1,
                "weather_code": 2,
                "wind_speed_10m": 8.0,
                "time": "2026-11-04T19:00",
            },
            "current_units": {"temperature_2m": "°C"},
            "backup_provider": "wttr.in",
            "backup_description": "Partly cloudy",
        }, True

    monkeypatch.setattr(weather_routes, "get_json_cached", cached_weather)

    response = client.get("/api/weather/current?city=Bengaluru")

    assert response.status_code == 200
    result = response.json()
    assert result["current"]["temperature_2m"] == 27.5
    assert result["observed_at"] == "2026-11-04T19:00"
    assert result["source"] == "wttr.in"
    assert result["backup_description"] == "Partly cloudy"
    assert result["using_cached_data"] is True


@pytest.mark.anyio
async def test_weather_cache_returns_cached_data_after_provider_failure(
    monkeypatch,
):
    import app.weather_cache as weather_cache

    weather_cache._cache.clear()

    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": 12.97, "longitude": 77.59}

    key = weather_cache._cache_key(url, params)

    weather_cache._cache[key] = {
        "data": {"current": {"temperature_2m": 28}},
        "saved_at": weather_cache.time.time(),
        # Make it stale but still within the permitted stale window.
    }

    weather_cache._cache[key]["saved_at"] -= (
        weather_cache.FRESH_CACHE_SECONDS + 10
    )

    async def failed_primary(*args, **kwargs):
        raise ValueError("Simulated provider failure")

    async def failed_backup(*args, **kwargs):
        raise ValueError("Simulated backup failure")

    monkeypatch.setattr(
        weather_cache,
        "_request_open_meteo",
        failed_primary,
    )

    monkeypatch.setattr(
        weather_cache,
        "_request_backup",
        failed_backup,
    )

    result, using_cache = await get_json_cached(
        url,
        params,
        timeout=1,
    )

    assert result["current"]["temperature_2m"] == 28
    assert using_cache is True

    weather_cache._cache.clear()


@pytest.mark.anyio
async def test_weather_cache_fails_when_no_provider_or_cache_available(
    monkeypatch,
):
    import app.weather_cache as weather_cache

    weather_cache._cache.clear()

    async def failed_primary(*args, **kwargs):
        raise ValueError("Simulated provider failure")

    async def failed_backup(*args, **kwargs):
        raise ValueError("Simulated backup failure")

    monkeypatch.setattr(
        weather_cache,
        "_request_open_meteo",
        failed_primary,
    )

    monkeypatch.setattr(
        weather_cache,
        "_request_backup",
        failed_backup,
    )

    with pytest.raises(RuntimeError):
        await get_json_cached(
            "https://api.open-meteo.com/v1/forecast",
            {"latitude": 12.97, "longitude": 77.59},
            timeout=1,
        )