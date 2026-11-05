(() => {
    "use strict";

    const API_BASE = "/api/weather/current";

    const elements = {
        location: document.getElementById("weather-location"),
        message: document.getElementById("weather-message"),
        details: document.getElementById("weather-details"),
        icon: document.getElementById("weather-icon"),
        temperature: document.getElementById("weather-temperature"),
        condition: document.getElementById("weather-condition"),
        feelsLike: document.getElementById("weather-feels-like"),
        humidity: document.getElementById("weather-humidity"),
        wind: document.getElementById("weather-wind"),
        rain: document.getElementById("weather-rain"),
        useLocation: document.getElementById("weather-use-location"),
        cityForm: document.getElementById("weather-city-form"),
        cityInput: document.getElementById("weather-city"),
        refresh: document.getElementById("weather-refresh")
    };

    if (Object.values(elements).some(element => !element)) {
        console.error(
            "Weather card elements are missing. Check the dashboard HTML."
        );
        return;
    }

    let lastSearch = { type: "city", value: "Hyderabad" };
    let requestNumber = 0;
    let lastSuccessfulMessage = "";

    function describeWeather(code, isDay) {
        const descriptions = {
            0: ["Clear sky", isDay ? "☀️" : "🌙"],
            1: ["Mainly clear", isDay ? "🌤️" : "🌙"],
            2: ["Partly cloudy", "⛅"],
            3: ["Overcast", "☁️"],
            45: ["Fog", "🌫️"],
            48: ["Depositing rime fog", "🌫️"],
            51: ["Light drizzle", "🌦️"],
            53: ["Moderate drizzle", "🌦️"],
            55: ["Dense drizzle", "🌧️"],
            56: ["Light freezing drizzle", "🌧️"],
            57: ["Dense freezing drizzle", "🌧️"],
            61: ["Slight rain", "🌧️"],
            63: ["Moderate rain", "🌧️"],
            65: ["Heavy rain", "🌧️"],
            66: ["Light freezing rain", "🌧️"],
            67: ["Heavy freezing rain", "🌧️"],
            71: ["Slight snowfall", "🌨️"],
            73: ["Moderate snowfall", "🌨️"],
            75: ["Heavy snowfall", "❄️"],
            77: ["Snow grains", "❄️"],
            80: ["Slight rain showers", "🌦️"],
            81: ["Moderate rain showers", "🌧️"],
            82: ["Violent rain showers", "⛈️"],
            85: ["Slight snow showers", "🌨️"],
            86: ["Heavy snow showers", "🌨️"],
            95: ["Thunderstorm", "⛈️"],
            96: ["Thunderstorm with hail", "⛈️"],
            99: ["Severe thunderstorm with hail", "⛈️"]
        };

        return descriptions[code] || ["Conditions unavailable", "🌡️"];
    }

    function showMessage(message, isError = false) {
        elements.message.hidden = false;
        elements.message.textContent = message;
        elements.message.style.color = isError ? "#b42318" : "#52657e";
    }

    async function loadWeather(params) {
        const thisRequest = ++requestNumber;
        showMessage(
            elements.details.hidden
                ? "Loading current weather..."
                : "Updating weather..."
        );

        const query = new URLSearchParams(params);

        try {
            const response = await fetch(`${API_BASE}?${query.toString()}`);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(
                    data.detail || "Unable to retrieve weather information."
                );
            }

            const current = data.current;
            const units = data.units || {};
            const location = data.location || {};

            if (!current || typeof current !== "object") {
                throw new Error("Weather provider returned no current conditions.");
            }
            if (thisRequest !== requestNumber) return;

            const [description, icon] = describeWeather(
                current.weather_code,
                current.is_day
            );

            const temperature = Number(current.temperature_2m);
            if (!Number.isFinite(temperature)) {
                throw new Error("Weather provider returned an invalid temperature.");
            }

            elements.location.textContent = [
                location.name,
                location.admin1,
                location.country
            ].filter(Boolean).join(", ") || "Selected location";

            elements.temperature.textContent =
                `${Math.round(temperature)}${units.temperature_2m || "°C"}`;

            elements.condition.textContent =
                data.backup_description || description;
            elements.icon.textContent = icon;

            elements.feelsLike.textContent =
                `${current.apparent_temperature ?? "—"}${units.apparent_temperature || "°C"}`;

            elements.humidity.textContent =
                `${current.relative_humidity_2m ?? "—"}${units.relative_humidity_2m || "%"}`;

            elements.wind.textContent =
                `${current.wind_speed_10m ?? "—"} ${units.wind_speed_10m || "km/h"}`;

            elements.rain.textContent =
                `${current.precipitation ?? "—"} ${units.precipitation || "mm"}`;

            elements.details.hidden = false;
            const observedAt = data.observed_at || current.time;
            const timeZone = data.timezone_abbreviation
                ? ` ${data.timezone_abbreviation}`
                : "";
            const observationLabel = observedAt
                ? `Observed ${observedAt}${timeZone}`
                : `Weather source: ${data.source || "weather provider"}`;

            if (data.using_cached_data) {
                lastSuccessfulMessage =
                    `${observationLabel}. Showing recent saved weather; ` +
                    "current conditions may have changed.";
            } else {
                lastSuccessfulMessage = observationLabel;
            }
            showMessage(lastSuccessfulMessage);
        } catch (error) {
            if (thisRequest !== requestNumber) return;
            console.error("Weather update failed:", error);
            showMessage(
                lastSuccessfulMessage
                    ? `Couldn't refresh. ${lastSuccessfulMessage}`
                    : "Weather is temporarily unavailable. Please try again.",
                !lastSuccessfulMessage
            );
        }
    }

    function useCurrentLocation() {
        if (!navigator.geolocation) {
            showMessage(
                "Your browser does not support location detection. Search for a city instead.",
                true
            );
            return;
        }

        showMessage("Requesting location permission...");

        navigator.geolocation.getCurrentPosition(
            position => {
                lastSearch = {
                    type: "coordinates",
                    value: {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    }
                };

                loadWeather(lastSearch.value);
            },
            () => {
                showMessage(
                    "Location access was denied or unavailable. Enter a city below.",
                    true
                );
            },
            {
                enableHighAccuracy: false,
                timeout: 10000,
                maximumAge: 300000
            }
        );
    }

    elements.cityForm.addEventListener("submit", event => {
        event.preventDefault();

        const city = elements.cityInput.value.trim();

        if (city.length < 2) {
            showMessage("Enter a city name with at least two characters.", true);
            elements.cityInput.focus();
            return;
        }

        lastSearch = { type: "city", value: city };
        loadWeather({ city });
    });

    elements.useLocation.addEventListener("click", useCurrentLocation);

    elements.refresh.addEventListener("click", () => {
        if (lastSearch.type === "coordinates") {
            loadWeather(lastSearch.value);
        } else {
            loadWeather({ city: lastSearch.value });
        }
    });

    // Load the dashboard's reference city first; users can select another location.
    loadWeather({ city: "Hyderabad" });
})();
