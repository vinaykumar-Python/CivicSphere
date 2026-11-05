"use strict";

const CIVICCARE_MAP_API = "";

document.addEventListener("DOMContentLoaded", async () => {
    const token = sessionStorage.getItem("civiccare_access_token");

    if (!token) {
        window.location.replace("index.html");
        return;
    }

    // Verify that the signed-in account belongs to an authority.
    try {
        const profileResponse = await fetch("/api/users/me", {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });

        if (!profileResponse.ok) {
            throw new Error("Unable to verify your account.");
        }

        const profile = await profileResponse.json();

        if (profile.role !== "authority") {
            window.location.replace("citizen-dashboard.html");
            return;
        }
    } catch (error) {
        sessionStorage.removeItem("civiccare_access_token");
        window.location.replace("index.html");
        return;
    }

    const mapElement = document.getElementById("authority-complaints-map");
    const messageElement = document.getElementById("map-message");
    const categoryFilter = document.getElementById("category-filter");
    const statusFilter = document.getElementById("status-filter");
    const refreshButton = document.getElementById("refresh-map");

    const totalElement = document.getElementById("total-complaints");
    const mappedElement = document.getElementById("mapped-complaints");
    const unmappedElement = document.getElementById("unmapped-complaints");

    let map = null;
    let markerLayer = null;
    let allComplaints = [];
    let loading = false;

    function showMessage(message, isError = false) {
        messageElement.textContent = message;
        messageElement.style.color = isError ? "#b42318" : "#46546a";
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

    function normalizeStatus(status) {
        return String(status || "")
            .trim()
            .toLowerCase()
            .replace(/[\s-]+/g, "_");
    }

    function statusLabel(status) {
        return String(status || "Unknown")
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, character => character.toUpperCase());
    }

    function markerColor(status) {
        switch (normalizeStatus(status)) {
            case "submitted":
                return "#2563eb";
            case "in_progress":
                return "#d97706";
            case "resolved":
                return "#16a34a";
            case "rejected":
                return "#dc2626";
            default:
                return "#64748b";
        }
    }

    function hasValidCoordinates(complaint) {
        if (
            complaint.latitude === null ||
            complaint.latitude === undefined ||
            complaint.longitude === null ||
            complaint.longitude === undefined ||
            String(complaint.latitude).trim() === "" ||
            String(complaint.longitude).trim() === ""
        ) {
            return false;
        }

        const latitude = Number(complaint.latitude);
        const longitude = Number(complaint.longitude);

        return (
            Number.isFinite(latitude) &&
            Number.isFinite(longitude) &&
            latitude >= -90 &&
            latitude <= 90 &&
            longitude >= -180 &&
            longitude <= 180
        );
    }

    async function apiRequest(path) {
        const response = await fetch(`${CIVICCARE_MAP_API}${path}`, {
            headers: {
                Authorization: `Bearer ${token}`
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
            throw new Error("Your session expired. Please sign in again.");
        }

        if (!response.ok) {
            throw new Error(
                typeof data.detail === "string"
                    ? data.detail
                    : "Unable to load department complaints."
            );
        }

        return data;
    }

    async function fetchAllDepartmentComplaints() {
        const collected = [];
        let page = 1;
        let totalPages = 1;

        // The backend supports up to 100 complaints per page.
        do {
            const data = await apiRequest(
                `/api/authority/complaints?page=${page}&page_size=100`
            );

            const items = Array.isArray(data)
                ? data
                : data.items || [];

            collected.push(...items);

            const pagination = data.pagination || {};
            totalPages = Math.max(
                1,
                Number(pagination.total_pages) || 1
            );

            page += 1;

            if (page > totalPages) {
                break;
            }
        } while (true);

        return collected;
    }

    function updateSummary(complaints) {
        const mapped = complaints.filter(hasValidCoordinates);

        totalElement.textContent = complaints.length;
        mappedElement.textContent = mapped.length;
        unmappedElement.textContent = complaints.length - mapped.length;
    }

    function getFilteredComplaints() {
        const selectedCategory = categoryFilter.value.toLowerCase();
        const selectedStatus = normalizeStatus(statusFilter.value);

        return allComplaints.filter(complaint => {
            const category = String(complaint.category || "")
                .trim()
                .toLowerCase();

            const status = normalizeStatus(complaint.status);

            const matchesCategory =
                selectedCategory === "all" ||
                category === selectedCategory;

            const matchesStatus =
                selectedStatus === "all" ||
                status === selectedStatus;

            return matchesCategory && matchesStatus;
        });
    }

    function createPopup(complaint) {
        const id = escapeHTML(complaint.id);
        const title = escapeHTML(complaint.title || "Untitled complaint");
        const category = escapeHTML(complaint.category || "Unknown");
        const status = escapeHTML(statusLabel(complaint.status));
        const location = escapeHTML(complaint.location || "Not provided");
        const description = escapeHTML(
            complaint.description || "No description provided."
        );

        const latitude = Number(complaint.latitude).toFixed(6);
        const longitude = Number(complaint.longitude).toFixed(6);

        return `
            <div style="min-width:220px;max-width:300px;line-height:1.5">
                <strong style="font-size:16px">
                    ${title}
                </strong>

                <hr>

                <div><strong>Complaint ID:</strong> ${id}</div>
                <div><strong>Category:</strong> ${category}</div>
                <div><strong>Status:</strong> ${status}</div>
                <div><strong>Location:</strong> ${location}</div>

                <p style="margin:8px 0">
                    ${description}
                </p>

                <small>
                    Coordinates: ${latitude}, ${longitude}
                </small>
            </div>
        `;
    }

    function renderMarkers() {
        if (!map || !markerLayer) {
            return;
        }

        markerLayer.clearLayers();

        const filtered = getFilteredComplaints();
        const mappable = filtered.filter(hasValidCoordinates);

        for (const complaint of mappable) {
            const latitude = Number(complaint.latitude);
            const longitude = Number(complaint.longitude);

            const marker = L.circleMarker([latitude, longitude], {
                radius: 9,
                color: markerColor(complaint.status),
                fillColor: markerColor(complaint.status),
                fillOpacity: 0.85,
                weight: 2
            });

            marker.bindPopup(createPopup(complaint));
            marker.addTo(markerLayer);
        }

        if (mappable.length > 0) {
            const bounds = markerLayer.getBounds();

            if (bounds.isValid()) {
                map.fitBounds(bounds, {
                    padding: [35, 35],
                    maxZoom: 15
                });
            }

            showMessage(
                `Showing ${mappable.length} mapped complaint(s) out of ` +
                `${filtered.length} complaint(s) matching your filters.`
            );
        } else {
            showMessage(
                filtered.length === 0
                    ? "No complaints match the selected filters."
                    : "No matching complaints have valid coordinates. " +
                      "Try another filter or add locations to existing complaints."
            );
        }
    }

    async function loadComplaints() {
        if (loading) {
            return;
        }

        loading = true;
        refreshButton.disabled = true;
        refreshButton.textContent = "Loading...";
        showMessage("Loading department complaints...");

        try {
            allComplaints = await fetchAllDepartmentComplaints();

            updateSummary(allComplaints);
            renderMarkers();
        } catch (error) {
            console.error("Authority map loading failed:", error);
            showMessage(error.message, true);
        } finally {
            loading = false;
            refreshButton.disabled = false;
            refreshButton.textContent = "↻ Refresh Map";
        }
    }

    if (!mapElement || typeof L === "undefined") {
        showMessage(
            "The map library could not load. Check your internet connection and reload.",
            true
        );
        return;
    }

    map = L.map("authority-complaints-map").setView(
        [12.9716, 77.5946],
        11
    );

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">' +
            "OpenStreetMap</a> contributors"
    }).addTo(map);

    markerLayer = L.featureGroup().addTo(map);

    categoryFilter.addEventListener("change", renderMarkers);
    statusFilter.addEventListener("change", renderMarkers);

    refreshButton.addEventListener("click", loadComplaints);

    document.getElementById("back-to-dashboard")
        .addEventListener("click", () => {
            window.location.href = "authority-dashboard.html";
        });

    loadComplaints();
});