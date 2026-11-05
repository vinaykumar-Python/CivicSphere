"use strict";

const CIVICCARE_API = "";

document.addEventListener("DOMContentLoaded", () => {
    const token = sessionStorage.getItem("civiccare_access_token");

    if (!token) {
        window.location.replace("index.html");
        return;
    }

    const citizenName = document.getElementById("citizen-name");
    const complaintForm = document.getElementById("complaint-form");
    const complaintMessage = document.getElementById("complaint-message");
    const complaintsMessage = document.getElementById("complaints-message");
    const complaintsBody = document.getElementById("complaints-table-body");
    const categorySelect = document.getElementById("complaint-category");
    const submitButton = document.getElementById("submit-complaint-button");
        // Complaint location map
    const mapElement = document.getElementById("complaint-map");
    const latitudeInput = document.getElementById("complaint-latitude");
    const longitudeInput = document.getElementById("complaint-longitude");
    const getLocationButton = document.getElementById("get-my-location");
    const locationMessage = document.getElementById("location-message");

    let complaintMap = null;
    let complaintMarker = null;

    function updateSelectedLocation(latitude, longitude) {
        latitudeInput.value = latitude.toFixed(6);
        longitudeInput.value = longitude.toFixed(6);

        if (complaintMarker) {
            complaintMarker.setLatLng([latitude, longitude]);
        } else {
            complaintMarker = L.marker([latitude, longitude]).addTo(complaintMap);
        }

        complaintMarker.bindPopup("Selected complaint location").openPopup();

        locationMessage.textContent =
            `Location selected: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
    }

    function initializeComplaintMap() {
        if (!mapElement || typeof L === "undefined") {
            if (locationMessage) {
                locationMessage.textContent =
                    "The map could not load. Check your internet connection and reload the page.";
            }
            return;
        }

        // Default map center: Hyderabad. Citizens can select another location.
        complaintMap = L.map("complaint-map").setView([17.385, 78.4867], 12);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(complaintMap);

        complaintMap.on("click", event => {
            updateSelectedLocation(
                event.latlng.lat,
                event.latlng.lng
            );
        });
    }

    if (getLocationButton) {
        getLocationButton.addEventListener("click", () => {
            if (!navigator.geolocation) {
                locationMessage.textContent =
                    "Your browser does not support location detection. Select a point on the map instead.";
                return;
            }

            locationMessage.textContent = "Getting your location...";
            getLocationButton.disabled = true;

            navigator.geolocation.getCurrentPosition(
                position => {
                    const latitude = position.coords.latitude;
                    const longitude = position.coords.longitude;

                    if (complaintMap) {
                        complaintMap.setView([latitude, longitude], 16);
                        updateSelectedLocation(latitude, longitude);
                    }

                    getLocationButton.disabled = false;
                },
                error => {
                    const messages = {
                        1: "Location permission denied. Allow location access or select a point on the map.",
                        2: "Your location is unavailable. Select a point on the map instead.",
                        3: "Location request timed out. Try again or select a point on the map."
                    };

                    locationMessage.textContent =
                        messages[error.code] || "Could not get your location.";

                    getLocationButton.disabled = false;
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 60000
                }
            );
        });
    }

    initializeComplaintMap();

    function showMessage(element, message, type = "info") {
        element.textContent = message;
        element.className = "auth-message";

        if (type === "error") element.classList.add("error");
        if (type === "success") element.classList.add("success");

        element.hidden = false;
    }

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[character]);
    }

    async function apiRequest(path, options = {}) {
        const response = await fetch(`${CIVICCARE_API}${path}`, {
            ...options,
            headers: {
                Authorization: `Bearer ${token}`,
                ...(options.headers || {})
            }
        });

        const text = await response.text();
        let data = {};

        if (text) {
            try {
                data = JSON.parse(text);
            } catch {
                data = { detail: text };
            }
        }

        if (response.status === 401) {
            sessionStorage.removeItem("civiccare_access_token");
            window.location.replace("index.html");
            throw new Error("Your session has expired. Please sign in again.");
        }

        if (!response.ok) {
            let message = data.detail || "The request could not be completed.";

            if (Array.isArray(message)) {
                message = message.map(item => item.msg || "Invalid input").join(". ");
            }

            throw new Error(message);
        }

        return data;
    }

    function normalizeStatus(status) {
        return String(status || "unknown")
            .trim()
            .toLowerCase()
            .replace(/[_\s]+/g, "-");
    }

    function statusLabel(status) {
        return String(status || "Unknown")
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, letter => letter.toUpperCase());
    }

    function statusClass(status) {
        const normalized = normalizeStatus(status);

        if (normalized === "submitted" || normalized === "pending") {
            return "status-submitted";
        }

        if (
            normalized === "in-progress" ||
            normalized === "processing" ||
            normalized === "under-review"
        ) {
            return "status-in-progress";
        }

        if (normalized === "resolved" || normalized === "closed") {
            return "status-resolved";
        }

        if (normalized === "rejected") {
            return "status-rejected";
        }

        return "status-default";
    }

    function formatDate(value) {
        if (!value) return "—";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return String(value);
        }

        return date.toLocaleDateString(undefined, {
            day: "numeric",
            month: "short",
            year: "numeric"
        });
    }

    async function loadProfile() {
        const profile = await apiRequest("/api/users/me");

        if (profile.role !== "citizen") {
            sessionStorage.removeItem("civiccare_access_token");
            window.location.replace(
                profile.role === "authority"
                    ? "authority-dashboard.html"
                    : "index.html"
            );
            throw new Error("This account uses a different CivicCare portal.");
        }

        citizenName.textContent =
            profile.full_name || profile.name || "Citizen";
    }

    async function loadCategories() {
        try {
            const categories = await apiRequest("/api/categories/", {
                headers: {}
            });

            categorySelect.replaceChildren();

            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "Select an issue category";
            categorySelect.appendChild(placeholder);

            const items = Array.isArray(categories)
                ? categories
                : categories.items || categories.categories || [];

            for (const item of items) {
                const value = typeof item === "string"
                    ? item
                    : item.value || item.name || item.label;

                const label = typeof item === "string"
                    ? item
                    : item.label || item.name || item.value;

                if (!value) continue;

                const option = document.createElement("option");
                option.value = value;
                option.textContent = label || value;
                categorySelect.appendChild(option);
            }

            if (categorySelect.options.length === 1) {
                throw new Error("The category endpoint returned no categories.");
            }
        } catch (error) {
            console.error("Category loading failed:", error);

            categorySelect.innerHTML = `
                <option value="">Choose a category</option>
                <option value="garbage">Garbage</option>
                <option value="roads">Roads</option>
                <option value="streetlights">Streetlights</option>
                <option value="water supply">Water supply</option>
                <option value="drainage">Drainage</option>
                <option value="public safety">Public safety</option>
                <option value="other">Other</option>
            `;
        }
    }
async function loadDashboardStats() {
    try {
        const response = await apiRequest("/api/dashboard/citizen");

        const stats = response.summary ?? response;

        document.getElementById("stat-total").textContent =
            stats.total_complaints ?? stats.total ?? 0;

        document.getElementById("stat-submitted").textContent =
            stats.submitted ?? stats.submitted_complaints ?? 0;

        document.getElementById("stat-progress").textContent =
            stats.in_progress ?? stats.in_progress_complaints ?? 0;

        document.getElementById("stat-resolved").textContent =
            stats.resolved ?? stats.resolved_complaints ?? 0;

        document.getElementById("stat-rejected").textContent =
            stats.rejected ?? stats.rejected_complaints ?? 0;

        renderRecentComplaints(response.recent_complaints || []);
    } catch (error) {
        console.error("Dashboard statistics failed:", error);

        const recentBody = document.getElementById("recent-complaints-table-body");
        if (recentBody) {
            recentBody.innerHTML =
                '<tr><td colspan="5" class="table-empty">Recent complaints could not be loaded.</td></tr>';
        }

        showMessage(
            complaintsMessage,
            "Your complaint statistics could not be loaded. Please try again.",
            "error"
        );
    }
}

function renderRecentComplaints(complaints) {
    const body = document.getElementById("recent-complaints-table-body");
    if (!body) return;

    body.replaceChildren();

    if (!Array.isArray(complaints) || complaints.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.className = "table-empty";
        cell.textContent = "No complaints yet. Submit a report to get started.";
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }

    for (const complaint of complaints.slice(0, 3)) {
        const row = document.createElement("tr");
        const idCell = document.createElement("td");
        idCell.textContent = complaint.id ? `#${complaint.id}` : "—";

        const titleCell = document.createElement("td");
        titleCell.textContent = complaint.title || "Untitled complaint";

        const categoryCell = document.createElement("td");
        categoryCell.textContent = complaint.category || "Other";

        const statusCell = document.createElement("td");
        const status = complaint.status || "submitted";
        const badge = document.createElement("span");
        badge.className = `complaint-status ${statusClass(status)}`;
        badge.textContent = statusLabel(status);
        statusCell.appendChild(badge);

        const dateCell = document.createElement("td");
        dateCell.textContent = formatDate(complaint.created_at);

        row.append(idCell, titleCell, categoryCell, statusCell, dateCell);
        body.appendChild(row);
    }
}

async function loadCitizenAnalytics() {
    const chart = document.getElementById("citizen-status-chart");
    const message = document.getElementById("citizen-analytics-message");
    const categoryChart = document.getElementById("category-analytics-chart");
    const categoryEmpty = document.getElementById("analytics-category-empty");

    try {
        const response = await apiRequest("/api/analytics/citizen");
        const summary = response.summary || response;
        const count = value => {
            const parsed = Number(value);
            return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
        };
        const statuses = [
            {
                key: "resolved",
                label: "Resolved",
                value: count(summary.resolved),
                color: "#31bd64"
            },
            {
                key: "progress",
                label: "In progress",
                value: count(summary.in_progress),
                color: "#3d8df4"
            },
            {
                key: "submitted",
                label: "Submitted",
                value: count(summary.submitted),
                color: "#ffab18"
            },
            {
                key: "rejected",
                label: "Rejected",
                value: count(summary.rejected),
                color: "#df6262"
            }
        ];
        const total = count(summary.total_complaints);
        const stops = [];
        let cumulative = 0;

        statuses.forEach(status => {
            const start = cumulative;
            cumulative += total > 0 ? status.value / total * 100 : 0;
            stops.push(
                `${status.color} ${start}% ${cumulative}%`
            );

            const legendValue = document.getElementById(
                `citizen-legend-${status.key}`
            );
            if (legendValue) {
                legendValue.textContent =
                    status.value.toLocaleString("en-IN");
            }
        });

        chart.style.background = total > 0
            ? `conic-gradient(${stops.join(", ")})`
            : "";
        chart.classList.toggle("performance-donut-empty", total === 0);
        chart.setAttribute(
            "aria-label",
            `Your ${total} complaints: ` +
                statuses.map(status =>
                    `${status.value} ${status.label.toLowerCase()}`
                ).join(", ")
        );
        document.getElementById("citizen-chart-total").textContent =
            total.toLocaleString("en-IN");

        const categories = Array.isArray(response.by_category)
            ? response.by_category
                .map(item => ({
                    label: String(item.category || "Uncategorized")
                        .replace(/[_-]+/g, " ")
                        .replace(/\b\w/g, character => character.toUpperCase()),
                    value: count(item.total)
                }))
                .filter(item => item.value > 0)
            : [];

        categoryChart.replaceChildren();
        categoryEmpty.hidden = categories.length > 0;
        if (categories.length > 0) {
            const highestCount = Math.max(...categories.map(item => item.value));

            categories.forEach(category => {
                const row = document.createElement("div");
                row.className = "category-analytics-row";

                const label = document.createElement("span");
                label.className = "category-analytics-label";
                label.textContent = category.label;

                const track = document.createElement("span");
                track.className = "category-analytics-track";
                const fill = document.createElement("span");
                fill.className = "category-analytics-fill";
                fill.style.width =
                    `${category.value / highestCount * 100}%`;
                track.appendChild(fill);

                const value = document.createElement("strong");
                value.className = "category-analytics-value";
                value.textContent = category.value.toLocaleString("en-IN");

                row.append(label, track, value);
                categoryChart.appendChild(row);
            });
        }

        message.hidden = true;
        message.textContent = "";
    } catch (error) {
        console.error("Citizen analytics failed:", error);
        message.textContent =
            "Your analytics are temporarily unavailable. Please try again.";
        message.hidden = false;
    }
}

function updateLatestComplaint(complaints) {
    const title = document.getElementById("latest-complaint-title");
    const date = document.getElementById("latest-complaint-date");
    const status = document.getElementById("latest-complaint-status");
    const timeline = document.getElementById("latest-complaint-timeline");

    if (!title || !date || !status || !timeline) return;

    const latest = [...complaints].sort((first, second) =>
        new Date(second.created_at || 0) - new Date(first.created_at || 0)
    )[0];

    if (!latest) {
        title.textContent = "Your latest report will appear here";
        date.textContent = "Submit a complaint to get started";
        status.textContent = "No reports yet";
        status.className = "overview-status";
        timeline.dataset.status = "";
        return;
    }

    const normalizedStatus = String(latest.status || "submitted")
        .trim()
        .toLowerCase();

    title.textContent = latest.title || "Untitled complaint";
    date.textContent = `Filed on ${formatDate(latest.created_at)}`;
    status.textContent = statusLabel(normalizedStatus);
    status.className = `overview-status ${statusClass(normalizedStatus)}`;
    timeline.dataset.status = normalizedStatus;
}

function renderComplaints(complaints) {
    complaintsBody.replaceChildren();
    updateLatestComplaint(Array.isArray(complaints) ? complaints : []);

    if (!Array.isArray(complaints) || complaints.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 6;
            cell.className = "table-empty";
            cell.textContent =
                "You haven't submitted any complaints yet. Use the form above to report an issue.";

            row.appendChild(cell);
            complaintsBody.appendChild(row);
            return;
        }

        for (const complaint of complaints) {
            const row = document.createElement("tr");
            const status = complaint.status || "submitted";

            const values = [
                {
                    className: "complaint-title-cell",
                    text: complaint.title || "Untitled complaint"
                },
                {
                    className: "",
                    text: complaint.category || "—"
                },
                {
                    className: "",
                    text: complaint.department_name || "Awaiting assignment"
                },
                {
                    className: "",
                    text: formatDate(complaint.created_at)
                }
            ];

            for (const item of values) {
                const cell = document.createElement("td");
                cell.className = item.className;
                cell.textContent = item.text;
                row.appendChild(cell);
            }

            const statusCell = document.createElement("td");
            const badge = document.createElement("span");
            badge.className = `complaint-status ${statusClass(status)}`;
            badge.textContent = statusLabel(status);
            statusCell.appendChild(badge);
            row.appendChild(statusCell);

            const actionCell = document.createElement("td");
            const historyButton = document.createElement("button");

            historyButton.type = "button";
            historyButton.className = "table-action";
            historyButton.textContent = "View history";
            historyButton.addEventListener("click", () => {
                loadComplaintHistory(complaint.id, complaint.title);
            });

            actionCell.appendChild(historyButton);
            row.appendChild(actionCell);

            complaintsBody.appendChild(row);
        }
    }

    function filterCitizenComplaints() {
        const searchInput = document.querySelector(
            ".dashboard-header .dashboard-search input"
        );
        const query = searchInput?.value.trim().toLowerCase() || "";

        if (complaintsBody.querySelector(".table-empty")) {
            complaintsBody.querySelector(".complaint-search-empty")?.remove();
            return;
        }

        const rows = Array.from(complaintsBody.querySelectorAll("tr"))
            .filter(row => !row.classList.contains("complaint-search-empty"));
        const visibleRows = rows.filter(row => {
            const matches = row.textContent.toLowerCase().includes(query);
            row.hidden = !matches;
            return matches;
        });
        let emptyRow = complaintsBody.querySelector(
            ".complaint-search-empty"
        );

        if (query && visibleRows.length === 0) {
            if (!emptyRow) {
                emptyRow = document.createElement("tr");
                emptyRow.className = "complaint-search-empty";
                const cell = document.createElement("td");
                cell.colSpan = 6;
                cell.className = "table-empty";
                cell.textContent = "No complaints match your search.";
                emptyRow.appendChild(cell);
            }
            complaintsBody.appendChild(emptyRow);
        } else {
            emptyRow?.remove();
        }
    }

    async function loadComplaints() {
        complaintsBody.innerHTML = `
            <tr><td colspan="6" class="table-empty">Loading complaints...</td></tr>
        `;

        try {
            const data = await apiRequest("/api/complaints/my");

            const complaints = Array.isArray(data)
                ? data
                : data.items || data.complaints || [];

            renderComplaints(complaints);
            filterCitizenComplaints();
            complaintsMessage.hidden = true;
        } catch (error) {
            console.error("Complaint loading failed:", error);

            complaintsBody.innerHTML = `
                <tr><td colspan="6" class="table-empty">Your complaints could not be loaded. Please try again.</td></tr>
            `;

            showMessage(
                complaintsMessage,
                "Your complaints could not be loaded. Please refresh and try again.",
                "error"
            );
        }
    }

    async function loadComplaintHistory(complaintId, title) {
    const historySection = document.getElementById("complaint-history-section");
    const historyContent = document.getElementById("history-content");

    historySection.hidden = false;

    document.getElementById("history-title").textContent =
        `History: ${title || "Complaint"}`;

    historyContent.textContent = "Loading complaint timeline...";
    historySection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    try {
        const data = await apiRequest(
            `/api/complaints/${encodeURIComponent(complaintId)}/history`
        );

        const entries = Array.isArray(data.history)
            ? data.history
            : [];

        historyContent.replaceChildren();

        if (entries.length === 0) {
            historyContent.textContent =
                "No complaint timeline information is available.";
            return;
        }

        const timeline = document.createElement("div");
        timeline.className = "civic-timeline";

        for (const entry of entries) {
            const article = document.createElement("article");
            article.className = "history-entry";

            const marker = document.createElement("span");
            marker.className = "timeline-marker";

            const details = document.createElement("div");
            details.className = "timeline-details";

            const heading = document.createElement("strong");

            heading.textContent = entry.event_type === "submission"
                ? "Complaint Submitted"
                : `Status: ${statusLabel(entry.new_status)}`;

            const time = document.createElement("time");
            time.textContent = formatDate(entry.changed_at);

            const updater = document.createElement("p");
            updater.className = "timeline-updater";

            const role = String(entry.changed_by_role || "").toLowerCase();

            if (role === "authority") {
                updater.textContent =
                    `Updated by: ${entry.department_name || entry.changed_by_name || "Department Authority"}`;
            } else {
                updater.textContent =
                    `Submitted by: ${entry.changed_by_name || "Citizen"}`;
            }

            details.append(heading, time, updater);

            if (entry.old_status) {
                const previous = document.createElement("p");
                previous.textContent =
                    `Previous status: ${statusLabel(entry.old_status)}`;
                details.appendChild(previous);
            }

            if (entry.note) {
                const note = document.createElement("p");
                note.className = "timeline-note";
                note.textContent = entry.note;
                details.appendChild(note);
            }

            article.append(marker, details);
            timeline.appendChild(article);
        }

        historyContent.appendChild(timeline);

    } catch (error) {
        console.error("Complaint history could not be loaded:", error);
        historyContent.textContent =
            "Complaint history could not be loaded. Please try again.";
    }
}
    complaintForm.addEventListener("submit", async event => {
        event.preventDefault();
        complaintMessage.hidden = true;

        const title = document.getElementById("complaint-title").value.trim();
        const category = categorySelect.value;
        const location = document.getElementById("complaint-location").value.trim();
        const description = document.getElementById("complaint-description").value.trim();

        if (!title || !category || !location || !description) {
            showMessage(
                complaintMessage,
                "Please complete the title, category, location, and description.",
                "error"
            );
            return;
        }

        const originalText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = "Submitting complaint...";

        try {
            await apiRequest("/api/complaints/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
    title,
    category,
    location,
    description,
    latitude: latitudeInput.value ? Number(latitudeInput.value) : null,
    longitude: longitudeInput.value ? Number(longitudeInput.value) : null
})
            });

            complaintForm.reset();
            if (complaintMap) {
    if (complaintMarker) {
        complaintMap.removeLayer(complaintMarker);
        complaintMarker = null;
    }

    complaintMap.setView([12.9716, 77.5946], 12);
}

if (locationMessage) {
    locationMessage.textContent =
        "Enter an address or select a location on the map.";
}

            showMessage(
                complaintMessage,
                "Your complaint was submitted successfully.",
                "success"
            );

            await Promise.all([
                loadDashboardStats(),
                loadComplaints(),
                loadCitizenAnalytics()
            ]);
        } catch (error) {
            console.error("Complaint submission failed:", error);
            showMessage(
                complaintMessage,
                "Your complaint could not be submitted. Please check the information and try again.",
                "error"
            );
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        }
    });

    document.getElementById("open-complaint-button").addEventListener("click", () => {
        document.getElementById("complaint-form-section").scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

        document.getElementById("complaint-title").focus({
            preventScroll: true
        });
    });

    document.getElementById("refresh-complaints-button").addEventListener(
        "click",
        async () => {
            await Promise.all([
                loadDashboardStats(),
                loadComplaints(),
                loadCitizenAnalytics()
            ]);
        }
    );

    document.getElementById("close-history-button").addEventListener("click", () => {
        document.getElementById("complaint-history-section").hidden = true;
    });

    document.getElementById("logout-button").addEventListener("click", () => {
        sessionStorage.removeItem("civiccare_access_token");
        window.location.replace("index.html");
    });

    document.getElementById("quick-notifications-button").addEventListener(
        "click",
        () => {
            document.getElementById("notification-bell").click();
        }
    );

    document.querySelectorAll("[data-analytics-view]").forEach(tab => {
        tab.addEventListener("click", () => {
            const selectedView = tab.dataset.analyticsView;

            document.querySelectorAll("[data-analytics-view]").forEach(item => {
                const selected = item === tab;
                item.classList.toggle("is-active", selected);
                item.setAttribute("aria-selected", String(selected));
            });

            document.getElementById("analytics-status-view").hidden =
                selectedView !== "status";
            document.getElementById("analytics-category-view").hidden =
                selectedView !== "category";
        });
    });

    const dashboardSearch = document.querySelector(
        ".dashboard-header .dashboard-search input"
    );
    if (dashboardSearch) {
        dashboardSearch.addEventListener("input", filterCitizenComplaints);
    }

    async function initializeDashboard() {
        try {
            await loadProfile();

            await Promise.all([
                loadCategories(),
                loadDashboardStats(),
                loadComplaints(),
                loadCitizenAnalytics()
            ]);
        } catch (error) {
            console.error("Dashboard initialization failed:", error);

            showMessage(
                complaintsMessage,
                "Your dashboard could not be loaded. Please refresh and try again.",
                "error"
            );
        }
    }

    initializeDashboard();
});
