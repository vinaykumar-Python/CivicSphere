(() => {
    "use strict";

    const API_URL = "/api/risk/weather";

    const panel = document.getElementById("risk-dashboard");
    if (!panel) {
        console.info("Risk panel is not installed on this page.");
        return;
    }

    const locationEl = document.getElementById("risk-location");
    const overallEl = document.getElementById("risk-overall");
    const messageEl = document.getElementById("risk-message");
    const indicatorsEl = document.getElementById("risk-indicators");
    const refreshButton = document.getElementById("risk-refresh");

    if (!locationEl || !overallEl || !messageEl || !indicatorsEl || !refreshButton) {
        console.error("Risk dashboard elements are missing.");
        return;
    }

    let lastQuery = { city: "Hyderabad" };
    let requestNumber = 0;

    const rank = { Low: 0, Moderate: 1, High: 2, Severe: 3 };

    function setRiskStyle(element, level) {
        element.dataset.risk = level.toLowerCase();
    }

    function addIndicator(label, value, level, description) {
        const card = document.createElement("article");
        card.className = "risk-indicator";
        setRiskStyle(card, level);

        const heading = document.createElement("h4");
        heading.textContent = label;

        const badge = document.createElement("span");
        badge.className = "risk-badge";
        badge.textContent = level;

        const valueEl = document.createElement("strong");
        valueEl.textContent = value;

        const descriptionEl = document.createElement("p");
        descriptionEl.textContent = description;

        card.append(heading, badge, valueEl, descriptionEl);
        indicatorsEl.appendChild(card);
    }

    async function loadRisk(query = lastQuery) {
        lastQuery = query;
        const thisRequest = ++requestNumber;

        messageEl.hidden = false;
        messageEl.textContent = "Assessing current weather risks...";
        indicatorsEl.replaceChildren();
        overallEl.textContent = "Loading...";
        refreshButton.disabled = true;

        try {
            const params = new URLSearchParams(query);
            const response = await fetch(`${API_URL}?${params.toString()}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Risk assessment is unavailable.");
            }

            if (thisRequest !== requestNumber) return;

            locationEl.textContent = [
                data.location?.name,
                data.location?.admin1,
                data.location?.country
            ].filter(Boolean).join(", ") || "Selected location";

            overallEl.textContent = data.overall_risk || "Unknown";
            setRiskStyle(overallEl, data.overall_risk || "Low");

            const indicators = data.indicators || {};
            const risks = data.risks || [];

            const definitions = {
                Heat: {
                    value: `${indicators.apparent_temperature_c ?? "--"} °C feels like`,
                    description: "Feels-like temperature."
                },
                Wind: {
                    value: `${indicators.wind_speed_kmh ?? "--"} km/h`,
                    description: "Current wind speed."
                },
                Rainfall: {
                    value: `${indicators.current_precipitation_mm ?? "--"} mm`,
                    description: `Forecast over the next 6 hours: ${indicators.next_six_hour_precipitation_mm ?? "--"} mm.`
                }
            };

            risks.forEach(risk => {
                const definition = definitions[risk.type] || {
                    value: "",
                    description: risk.message || ""
                };

                addIndicator(
                    risk.type,
                    definition.value,
                    risk.level || "Low",
                    risk.message || definition.description
                );
            });

            if (!risks.length) {
                const note = document.createElement("p");
                note.textContent = "No weather alerts for the selected location.";
                indicatorsEl.appendChild(note);
            }

            const notice = document.createElement("p");
            notice.className = "risk-disclaimer";
            notice.textContent =
                "For awareness only. Follow official local alerts during emergencies.";
            indicatorsEl.appendChild(notice);

            const observationTime = data.observed_at
                ? ` Observed ${data.observed_at}` +
                  (data.timezone_abbreviation
                      ? ` ${data.timezone_abbreviation}.`
                      : ".")
                : "";
            messageEl.textContent = data.using_cached_data
                ? `Showing recent saved weather; conditions may have changed.${observationTime}`
                : `Weather alerts updated.${observationTime}`;
        } catch (error) {
            if (thisRequest !== requestNumber) return;
            console.error("Weather risk update failed:", error);
            overallEl.textContent = "Unavailable";
            messageEl.textContent = "Weather alerts are temporarily unavailable. Please try again.";
            indicatorsEl.replaceChildren();
        } finally {
            if (thisRequest === requestNumber) {
                refreshButton.disabled = false;
            }
        }
    }

    refreshButton.addEventListener("click", () => loadRisk(lastQuery));

    // Reuse the weather card's selected city or coordinates when available.
    const cityInput = document.getElementById("weather-city");
    const cityForm = document.getElementById("weather-city-form");
    const locationButton = document.getElementById("weather-use-location");

    if (cityForm && cityInput) {
        cityForm.addEventListener("submit", () => {
            const city = cityInput.value.trim();
            if (city.length >= 2) {
                loadRisk({ city });
            }
        });
    }

    if (locationButton && navigator.geolocation) {
        locationButton.addEventListener("click", () => {
            navigator.geolocation.getCurrentPosition(
                position => loadRisk({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                }),
                () => {
                    messageEl.textContent =
                        "Location unavailable. Risk assessment remains on the last selected city.";
                },
                { timeout: 10000, maximumAge: 300000 }
            );
        });
    }

    loadRisk();
})();