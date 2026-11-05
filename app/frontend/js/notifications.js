"use strict";

(() => {
    const TOKEN_KEY = "civiccare_access_token";
    const API_URL = "/api/notifications";
    const REFRESH_INTERVAL = 30000;

    let refreshTimer = null;
    let isOpen = false;

    function getToken() {
        return sessionStorage.getItem(TOKEN_KEY);
    }

    async function apiRequest(path, options = {}) {
        const token = getToken();

        if (!token) {
            throw new Error("Your session has expired. Please log in again.");
        }

        const response = await fetch(`${API_URL}${path}`, {
            ...options,
            headers: {
                Authorization: `Bearer ${token}`,
                ...(options.headers || {})
            }
        });

        if (!response.ok) {
            const result = await response.json().catch(() => ({}));
            throw new Error(
                result.detail || `Notification request failed (${response.status}).`
            );
        }

        return response.json();
    }

    function createPanel() {
        if (document.getElementById("notification-panel")) return;

        const panel = document.createElement("section");
        panel.id = "notification-panel";
        panel.className = "notification-panel";
        panel.hidden = true;
        panel.setAttribute("aria-label", "Notifications");

        panel.innerHTML = `
            <div class="notification-panel-header">
                <div>
                    <h2>Notifications</h2>
                    <p id="notification-summary">Your latest updates</p>
                </div>
                <button
                    type="button"
                    id="notification-close"
                    class="notification-close"
                    aria-label="Close notifications"
                >&times;</button>
            </div>

            <div class="notification-toolbar">
                <span id="notification-unread-label">0 unread</span>
                <button type="button" id="notification-read-all">
                    Mark all as read
                </button>
            </div>

            <div id="notification-list" class="notification-list"
                 aria-live="polite">
                <p class="notification-loading">Loading notifications...</p>
            </div>

            <div class="notification-panel-footer">
                <button type="button" id="notification-refresh">
                    Refresh notifications
                </button>
            </div>
        `;

        document.body.appendChild(panel);
    }

    function updateBadge(count) {
        const badge = document.getElementById("notification-count");
        const unreadLabel = document.getElementById(
            "notification-unread-label"
        );

        if (!badge) return;

        badge.textContent = count > 99 ? "99+" : String(count);
        badge.hidden = count === 0;

        if (unreadLabel) {
            unreadLabel.textContent = `${count} unread`;
        }
    }

    function formatDate(value) {
        if (!value) return "Date unavailable";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return "Date unavailable";
        }

        return date.toLocaleString([], {
            dateStyle: "medium",
            timeStyle: "short"
        });
    }

    function renderNotifications(items) {
        const list = document.getElementById("notification-list");
        if (!list) return;

        list.replaceChildren();

        if (!items.length) {
            const empty = document.createElement("div");
            empty.className = "notification-empty";
            empty.textContent = "You're all caught up. No notifications yet.";
            list.appendChild(empty);
            return;
        }

        items.forEach(item => {
            const card = document.createElement("article");
            card.className = "notification-item";

            if (!item.is_read) {
                card.classList.add("notification-unread");
            }

            const content = document.createElement("div");
            content.className = "notification-content";

            const title = document.createElement("h3");
            title.textContent = item.title || "Notification";

            const message = document.createElement("p");
            message.textContent = item.message || "";

            const date = document.createElement("time");
            date.textContent = formatDate(item.created_at);
            date.dateTime = item.created_at || "";

            content.append(title, message, date);

            card.appendChild(content);

            if (!item.is_read) {
                const readButton = document.createElement("button");
                readButton.type = "button";
                readButton.className = "notification-mark-read";
                readButton.textContent = "Mark as read";

                readButton.addEventListener("click", async () => {
                    readButton.disabled = true;

                    try {
                        await apiRequest(
                            `/${encodeURIComponent(item.id)}/read`,
                            { method: "PATCH" }
                        );
                        await loadNotifications();
                    } catch (error) {
                        readButton.disabled = false;
                        console.error("Mark notification read:", error);
                    }
                });

                card.appendChild(readButton);
            } else {
                const readLabel = document.createElement("span");
                readLabel.className = "notification-read-label";
                readLabel.textContent = "Read";
                card.appendChild(readLabel);
            }

            list.appendChild(card);
        });
    }

    async function loadNotifications() {
        const list = document.getElementById("notification-list");

        try {
            const result = await apiRequest("/?page=1&page_size=20");

            renderNotifications(result.items || []);
            updateBadge(result.unread_count || 0);

            const summary = document.getElementById(
                "notification-summary"
            );

            if (summary) {
                summary.textContent =
                    `${result.pagination?.total_items || 0} recent notifications`;
            }
        } catch (error) {
            console.error("Notification loading error:", error);

            if (list) {
                list.textContent =
                    "Unable to load notifications. Please try again.";
            }
        }
    }

    async function markAllAsRead() {
        const button = document.getElementById("notification-read-all");
        if (button) button.disabled = true;

        try {
            await apiRequest("/read-all", { method: "PATCH" });
            await loadNotifications();
        } catch (error) {
            console.error("Mark all notifications read:", error);

            const list = document.getElementById("notification-list");
            if (list) {
                list.textContent =
                    "Unable to update notifications. Please try again.";
            }
        } finally {
            if (button) button.disabled = false;
        }
    }

    function closePanel() {
        const panel = document.getElementById("notification-panel");
        const bell = document.getElementById("notification-bell");

        if (!panel || !bell) return;

        panel.hidden = true;
        bell.setAttribute("aria-expanded", "false");
        isOpen = false;
    }

    function togglePanel() {
        const panel = document.getElementById("notification-panel");
        const bell = document.getElementById("notification-bell");

        if (!panel || !bell) return;

        isOpen = !isOpen;
        panel.hidden = !isOpen;
        bell.setAttribute("aria-expanded", String(isOpen));

        if (isOpen) {
            loadNotifications();
        }
    }

    function initialize() {
        const bell = document.getElementById("notification-bell");

        if (!bell || !getToken()) return;

        createPanel();

        bell.addEventListener("click", togglePanel);

        document.getElementById("notification-close")
            ?.addEventListener("click", closePanel);

        document.getElementById("notification-read-all")
            ?.addEventListener("click", markAllAsRead);

        document.getElementById("notification-refresh")
            ?.addEventListener("click", loadNotifications);

        document.addEventListener("keydown", event => {
            if (event.key === "Escape") closePanel();
        });

        document.addEventListener("click", event => {
            const panel = document.getElementById("notification-panel");

            if (
                isOpen &&
                panel &&
                !panel.contains(event.target) &&
                !bell.contains(event.target)
            ) {
                closePanel();
            }
        });

        loadNotifications();

        refreshTimer = window.setInterval(
            loadNotifications,
            REFRESH_INTERVAL
        );

        window.addEventListener("beforeunload", () => {
            if (refreshTimer) clearInterval(refreshTimer);
        });
    }

    document.addEventListener("DOMContentLoaded", initialize);
})();
