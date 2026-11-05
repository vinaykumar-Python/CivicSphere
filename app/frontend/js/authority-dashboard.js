"use strict";

/* =========================================================
   CIVICCARE AI — AUTHORITY DASHBOARD
   Features:
   - Authority authentication
   - Department complaint management
   - Search, filters and pagination
   - Complaint status updates
   - Emergency review indicators
   - SLA deadline and overdue monitoring
   - Escalation level tracking
   ========================================================= */

const AUTHORITY_API = "/api";
const AUTHORITY_TOKEN_KEY = "civiccare_access_token";

let currentPage = 1;
const pageSize = 20;
let totalPages = 0;
let searchTimer = null;
let refreshTimer = null;

const statusLabels = {
    submitted: "Submitted",
    in_progress: "In Progress",
    resolved: "Resolved",
    rejected: "Rejected"
};

const categoryLabels = {
    garbage: "Garbage",
    roads: "Roads",
    streetlights: "Streetlights",
    "water supply": "Water Supply",
    drainage: "Drainage",
    "public safety": "Public Safety",
    other: "Other"
};

const CLOSED_STATUSES = ["resolved", "rejected"];

/* =========================================================
   AUTHENTICATION
   ========================================================= */

function getAuthorityToken() {
    return sessionStorage.getItem(AUTHORITY_TOKEN_KEY);
}

function logoutAuthority() {
    sessionStorage.removeItem(AUTHORITY_TOKEN_KEY);

    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    window.location.replace("index.html");
}

/* =========================================================
   MESSAGES
   ========================================================= */

function showAuthorityMessage(message, type = "info") {
    const box = document.getElementById("authority-message");

    if (!box) return;

    box.textContent = message;
    box.className = `authority-message ${type}`;
    box.hidden = false;
}

function hideAuthorityMessage() {
    const box = document.getElementById("authority-message");

    if (!box) return;

    box.textContent = "";
    box.hidden = true;
}

/* =========================================================
   API REQUEST
   ========================================================= */

async function authorityRequest(path, options = {}) {
    const token = getAuthorityToken();

    if (!token) {
        logoutAuthority();
        throw new Error("Your session has expired. Please log in again.");
    }

    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${token}`);

    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${AUTHORITY_API}${path}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        logoutAuthority();
        throw new Error("Your session has expired. Please log in again.");
    }

    const contentType = response.headers.get("content-type") || "";
    let result = null;

    if (contentType.includes("application/json")) {
        result = await response.json();
    } else {
        const responseText = await response.text();

        if (responseText) {
            result = { detail: responseText };
        }
    }

    if (!response.ok) {
        throw new Error(
            result?.detail || `Request failed (${response.status}).`
        );
    }

    return result;
}

/* =========================================================
   FORMATTERS
   ========================================================= */

function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short"
    });
}

function formatRelativeTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Recently";

    const elapsedMinutes = Math.max(
        0,
        Math.floor((Date.now() - date.getTime()) / 60000)
    );

    if (elapsedMinutes < 60) return `${elapsedMinutes}m ago`;
    if (elapsedMinutes < 1440) {
        return `${Math.floor(elapsedMinutes / 60)}h ago`;
    }

    return `${Math.floor(elapsedMinutes / 1440)}d ago`;
}

function formatStatus(status) {
    const normalized = String(status || "").toLowerCase();

    return statusLabels[normalized] || normalized || "Unknown";
}

function formatCategory(category) {
    const normalized = String(category || "").toLowerCase();

    return categoryLabels[normalized] || normalized || "Other";
}

function setStat(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = Number(value || 0).toLocaleString("en-IN");
    }
}

function createCell(text) {
    const cell = document.createElement("td");
    cell.textContent = text ?? "—";
    return cell;
}

function createBadge(text, className) {
    const badge = document.createElement("span");

    badge.className = `sla-badge ${className}`;
    badge.textContent = text;

    return badge;
}

/* =========================================================
   COMPLAINT DUE DATES
   ========================================================= */

function isComplaintClosed(complaint) {
    const status = String(complaint.status || "").toLowerCase();

    return CLOSED_STATUSES.includes(status);
}

function isComplaintOverdue(complaint) {
    if (isComplaintClosed(complaint)) {
        return false;
    }

    if (!complaint.sla_deadline) {
        return false;
    }

    const deadline = new Date(complaint.sla_deadline);

    if (Number.isNaN(deadline.getTime())) {
        return false;
    }

    return Date.now() > deadline.getTime();
}

function createDueDateCell(complaint) {
    const cell = document.createElement("td");
    cell.className = "authority-due-date";

    const priority = String(complaint.priority || "normal").toLowerCase();

    const emergencyRequired =
        complaint.emergency_review_required === true ||
        priority === "emergency" ||
        priority === "critical";

    if (emergencyRequired) {
        cell.appendChild(
            createBadge("Urgent review required", "sla-emergency")
        );
        cell.appendChild(document.createElement("br"));
    }

    const deadline = complaint.sla_deadline;

    if (deadline) {
        const overdue = isComplaintOverdue(complaint);
        if (overdue) {
            cell.appendChild(createBadge("Overdue", "sla-overdue"));
            cell.appendChild(document.createElement("br"));
        }

        const deadlineText = document.createElement("div");
        deadlineText.className = "sla-muted";
        deadlineText.textContent = `Due ${formatDate(deadline)}`;

        cell.appendChild(deadlineText);
    } else {
        const unavailable = document.createElement("div");
        unavailable.className = "sla-muted";
        unavailable.textContent = "No due date";

        cell.appendChild(unavailable);
    }

    return cell;
}

/* =========================================================
   AUTHORITY PROFILE
   ========================================================= */

async function loadAuthorityProfile() {
    const profile = await authorityRequest("/authority/me");

    if (profile.role !== "authority") {
        sessionStorage.removeItem(AUTHORITY_TOKEN_KEY);
        window.location.replace(
            profile.role === "citizen"
                ? "citizen-dashboard.html"
                : "index.html"
        );
        throw new Error("This account uses a different CivicCare portal.");
    }

    const nameElement = document.getElementById("authority-user-name");
    const departmentElement =
        document.getElementById("authority-department-name");
    const welcomeNameElement =
        document.getElementById("authority-welcome-name");
    const welcomeDepartmentElement =
        document.getElementById("authority-welcome-department");

    if (nameElement) {
        nameElement.textContent =
            profile.full_name || "Department Authority";
    }

    if (welcomeNameElement) {
        welcomeNameElement.textContent =
            (profile.full_name || "Authority").split(/\s+/)[0];
    }

    if (departmentElement) {
        departmentElement.textContent =
            profile.department_name || "Department not assigned";
    }

    if (welcomeDepartmentElement) {
        welcomeDepartmentElement.textContent =
            profile.department_name || "Department not assigned";
    }
}

/* =========================================================
   DASHBOARD STATISTICS
   ========================================================= */

function updateAuthorityInsights(summary, recentComplaints = []) {
    const total = Number(
        summary.total_complaints ?? summary.total ?? summary.total_count ?? 0
    );
    const resolved = Number(summary.resolved ?? summary.resolved_count ?? 0);
    const inProgress = Number(
        summary.in_progress ?? summary.in_progress_count ?? 0
    );
    const submitted = Number(summary.submitted ?? summary.submitted_count ?? 0);
    const rejected = Number(summary.rejected ?? summary.rejected_count ?? 0);
    const percentage = total > 0
        ? Math.round((resolved / total) * 100)
        : 0;
    const inProgressEnd = total > 0
        ? Math.round(((resolved + inProgress) / total) * 100)
        : 0;
    const submittedEnd = total > 0
        ? Math.round(((resolved + inProgress + submitted) / total) * 100)
        : 0;

    const chart = document.getElementById("authority-performance-chart");
    const percentageLabel = document.getElementById(
        "authority-performance-percent"
    );
    if (chart && percentageLabel) {
        chart.style.setProperty("--resolved-percent", `${percentage}%`);
        chart.style.setProperty("--progress-end", `${inProgressEnd}%`);
        chart.style.setProperty("--submitted-end", `${submittedEnd}%`);
        chart.classList.toggle("performance-donut-empty", total === 0);
        chart.setAttribute(
            "aria-label",
            `${percentage}% resolved; ${inProgress} in progress, ` +
                `${submitted} submitted, and ${rejected} rejected`
        );
        percentageLabel.textContent = `${percentage}%`;
    }

    const legendValues = [
        ["authority-legend-resolved", resolved],
        ["authority-legend-progress", inProgress],
        ["authority-legend-submitted", submitted],
        ["authority-legend-rejected", rejected]
    ];
    legendValues.forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.textContent = Number(value).toLocaleString("en-IN");
    });

    const activityList = document.getElementById("authority-recent-activity");
    if (activityList) {
        activityList.replaceChildren();

        if (recentComplaints.length === 0) {
            const item = document.createElement("li");
            item.textContent = "No recent activity";
            activityList.appendChild(item);
        } else {
            recentComplaints.slice(0, 2).forEach(complaint => {
                const item = document.createElement("li");
                const summary = document.createElement("span");
                const title = document.createElement("strong");
                const details = document.createElement("small");

                title.textContent = complaint.title || "Untitled complaint";
                details.textContent =
                    `${formatStatus(complaint.status)} · ${formatRelativeTime(complaint.created_at)}`;
                summary.append(title, details);
                item.appendChild(summary);
                activityList.appendChild(item);
            });
        }
    }
}

async function loadAuthorityStatistics() {
    const response = await authorityRequest("/dashboard/authority");
    const stats = response.summary || response;

    setStat(
        "authority-stat-total",
        stats.total_complaints ?? stats.total ?? stats.total_count ?? 0
    );

    setStat(
        "authority-stat-submitted",
        stats.submitted ?? stats.submitted_count ?? 0
    );

    setStat(
        "authority-stat-progress",
        stats.in_progress ?? stats.in_progress_count ?? 0
    );

    setStat(
        "authority-stat-resolved",
        stats.resolved ?? stats.resolved_count ?? 0
    );

    setStat(
        "authority-stat-rejected",
        stats.rejected ?? stats.rejected_count ?? 0
    );
    setStat("authority-overdue-count", stats.overdue ?? 0);

    updateAuthorityInsights(
        stats,
        Array.isArray(response.recent_complaints)
            ? response.recent_complaints
            : []
    );
}

/* =========================================================
   COMPLAINT TABLE ROW
   ========================================================= */

function createComplaintRow(complaint) {
    const row = document.createElement("tr");

    /* ID and date */

    const idDateCell = document.createElement("td");

    const complaintId = document.createElement("strong");
    complaintId.textContent = `#${complaint.id}`;

    const date = document.createElement("div");
    date.className = "sla-muted";
    date.textContent = formatDate(complaint.created_at);

    idDateCell.append(complaintId, date);

    /* Complaint title and description */

    const complaintCell = document.createElement("td");

    const title = document.createElement("strong");
    title.textContent = complaint.title || "Untitled complaint";

    const description = document.createElement("div");
    description.textContent =
        complaint.description || "No description provided.";

    complaintCell.append(title, description);

    /* Category and location */

    const categoryCell = createCell(
        formatCategory(complaint.category)
    );

    const locationCell = createCell(
        complaint.location || "—"
    );

    /* Status badge */

    const statusCell = document.createElement("td");

    const normalizedStatus =
        String(complaint.status || "submitted").toLowerCase();

    const badge = document.createElement("span");
    badge.className = `authority-status ${normalizedStatus}`;
    badge.textContent = formatStatus(normalizedStatus);

    statusCell.appendChild(badge);

    /* SLA information */

    const slaCell = createDueDateCell(complaint);

    /* Status update controls */

    const actionCell = document.createElement("td");

    const statusSelect = document.createElement("select");

    statusSelect.setAttribute(
        "aria-label",
        `Update status for complaint ${complaint.id}`
    );

    const allowedStatuses = [
        "submitted",
        "in_progress",
        "resolved",
        "rejected"
    ];

    allowedStatuses.forEach(status => {
        const option = document.createElement("option");

        option.value = status;
        option.textContent = formatStatus(status);

        statusSelect.appendChild(option);
    });

    statusSelect.value = allowedStatuses.includes(normalizedStatus)
        ? normalizedStatus
        : "submitted";

    const updateButton = document.createElement("button");

    updateButton.type = "button";
    updateButton.className = "authority-button";
    updateButton.textContent = "Save";
    updateButton.style.marginTop = "8px";

    if (isComplaintClosed(complaint)) {
        statusSelect.disabled = true;
        updateButton.disabled = true;
        updateButton.textContent = "Closed";
    }

    updateButton.addEventListener("click", async () => {
        const newStatus = statusSelect.value;

        if (newStatus === normalizedStatus) {
            showAuthorityMessage(
                "Select a different status before saving.",
                "info"
            );
            return;
        }

        const confirmed = window.confirm(
            `Update complaint #${complaint.id} to "${formatStatus(newStatus)}"?`
        );

        if (!confirmed) {
            statusSelect.value = normalizedStatus;
            return;
        }

        updateButton.disabled = true;
        statusSelect.disabled = true;
        updateButton.textContent = "Saving...";

        try {
            const result = await authorityRequest(
                `/authority/complaints/${complaint.id}/status`,
                {
                    method: "PATCH",
                    body: JSON.stringify({ status: newStatus })
                }
            );

            showAuthorityMessage(
                result.message || "Complaint status updated successfully.",
                "success"
            );

            await Promise.all([
                loadAuthorityStatistics(),
                loadAuthorityComplaints()
            ]);

        } catch (error) {
            console.error("Complaint status update failed:", error);
            showAuthorityMessage(
                "The complaint status could not be updated. Please try again.",
                "error"
            );

            updateButton.disabled = false;
            statusSelect.disabled = false;
            updateButton.textContent = "Save";
        }
    });

    actionCell.append(
        statusSelect,
        document.createElement("br"),
        updateButton
    );

    row.append(
        idDateCell,
        complaintCell,
        categoryCell,
        locationCell,
        statusCell,
        slaCell,
        actionCell
    );

    return row;
}

/* =========================================================
   COMPLAINT LIST
   ========================================================= */

async function loadAuthorityComplaints() {
    const body = document.getElementById("authority-complaints-body");

    const paginationInfo =
        document.getElementById("authority-pagination-info");

    if (!body) return;

    body.replaceChildren();

    const loadingRow = document.createElement("tr");
    const loadingCell = document.createElement("td");

    loadingCell.colSpan = 7;
    loadingCell.className = "authority-empty";
    loadingCell.textContent = "Loading department complaints...";

    loadingRow.appendChild(loadingCell);
    body.appendChild(loadingRow);

    const params = new URLSearchParams({
        page: String(currentPage),
        page_size: String(pageSize)
    });

    const searchElement = document.getElementById("authority-search");
    const statusElement =
        document.getElementById("authority-status-filter");
    const categoryElement =
        document.getElementById("authority-category-filter");

    const search = searchElement?.value.trim() || "";
    const status = statusElement?.value || "";
    const category = categoryElement?.value || "";

    if (search) params.set("search", search);
    if (status) params.set("status_filter", status);
    if (category) params.set("category", category);

    try {
        const result = await authorityRequest(
            `/authority/complaints?${params.toString()}`
        );

        const complaints = Array.isArray(result.items)
            ? result.items
            : [];

        const pagination = result.pagination || {};

        totalPages = Number(pagination.total_pages || 0);

        body.replaceChildren();

        if (complaints.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 7;
            cell.className = "authority-empty";
            cell.textContent =
                "No complaints match your current filters.";

            row.appendChild(cell);
            body.appendChild(row);

        } else {
            complaints.forEach(complaint => {
                body.appendChild(createComplaintRow(complaint));
            });
        }

        const totalItems = Number(pagination.total_items || 0);

        if (paginationInfo) {
            paginationInfo.textContent =
                `Page ${currentPage} of ${totalPages} · ${totalItems} matching complaint(s)`;
        }

        const previousButton =
            document.getElementById("authority-previous-page");

        const nextButton =
            document.getElementById("authority-next-page");

        if (previousButton) {
            previousButton.disabled = currentPage <= 1;
        }

        if (nextButton) {
            nextButton.disabled =
                totalPages === 0 || currentPage >= totalPages;
        }

    } catch (error) {
        body.replaceChildren();

        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 7;
        cell.className = "authority-empty";
        cell.textContent = "Complaints could not be loaded. Please try again.";

        row.appendChild(cell);
        body.appendChild(row);

        if (paginationInfo) {
            paginationInfo.textContent =
                "Unable to load complaint information.";
        }

        document.getElementById("authority-previous-page").disabled = true;
        document.getElementById("authority-next-page").disabled = true;

        console.error("Department complaints could not be loaded:", error);
        showAuthorityMessage(
            "Department complaints could not be loaded. Please refresh and try again.",
            "error"
        );
    }
}

/* =========================================================
   DASHBOARD REFRESH
   ========================================================= */

async function refreshAuthorityDashboard() {
    hideAuthorityMessage();

    const refreshButton =
        document.getElementById("authority-refresh-button");

    if (refreshButton) {
        refreshButton.disabled = true;
        refreshButton.textContent = "Refreshing...";
    }

    try {
        await Promise.all([
            loadAuthorityProfile(),
            loadAuthorityStatistics(),
            loadAuthorityComplaints()
        ]);

    } catch (error) {
        console.error("Authority dashboard refresh failed:", error);
        showAuthorityMessage(
            "Your dashboard could not be refreshed. Please try again.",
            "error"
        );

    } finally {
        if (refreshButton) {
            refreshButton.disabled = false;
            refreshButton.textContent = "Refresh";
        }
    }
}

/* =========================================================
   AUTOMATIC SLA DISPLAY REFRESH
   ========================================================= */

function startAuthorityAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    // Refresh displayed SLA countdowns and complaint information.
    refreshTimer = setInterval(() => {
        if (!document.hidden && getAuthorityToken()) {
            loadAuthorityComplaints();
            loadAuthorityStatistics().catch(error => {
                console.error("Statistics refresh failed:", error);
            });
        }
    }, 60000);
}

/* =========================================================
   INITIALIZATION
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {
    const dashboardSearch = document.querySelector(".authority-header .dashboard-search input");
    const complaintSearch = document.getElementById("authority-search");
    if (dashboardSearch && complaintSearch) {
        dashboardSearch.addEventListener("input", () => {
            complaintSearch.value = dashboardSearch.value;
            complaintSearch.dispatchEvent(new Event("input", { bubbles: true }));
        });
    }

    const logoutButton =
        document.getElementById("authority-logout-button");

    const refreshButton =
        document.getElementById("authority-refresh-button");

    const applyFiltersButton =
        document.getElementById("authority-apply-filters");

    const statusFilter =
        document.getElementById("authority-status-filter");

    const categoryFilter =
        document.getElementById("authority-category-filter");

    const searchInput =
        document.getElementById("authority-search");

    const previousButton =
        document.getElementById("authority-previous-page");

    const nextButton =
        document.getElementById("authority-next-page");

    logoutButton?.addEventListener("click", logoutAuthority);

    refreshButton?.addEventListener(
        "click",
        refreshAuthorityDashboard
    );

    applyFiltersButton?.addEventListener("click", () => {
        currentPage = 1;
        loadAuthorityComplaints();
    });

    statusFilter?.addEventListener("change", () => {
        currentPage = 1;
        loadAuthorityComplaints();
    });

    categoryFilter?.addEventListener("change", () => {
        currentPage = 1;
        loadAuthorityComplaints();
    });

    searchInput?.addEventListener("input", () => {
        clearTimeout(searchTimer);

        searchTimer = setTimeout(() => {
            currentPage = 1;
            loadAuthorityComplaints();
        }, 350);
    });

    previousButton?.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            loadAuthorityComplaints();
        }
    });

    nextButton?.addEventListener("click", () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadAuthorityComplaints();
        }
    });

    if (!getAuthorityToken()) {
        logoutAuthority();
        return;
    }

    refreshAuthorityDashboard();
    startAuthorityAutoRefresh();
});

function filterAuthorityComplaints(status) {
    const statusFilter = document.getElementById(
        "authority-status-filter"
    );

    const applyButton = document.getElementById(
        "authority-apply-filters"
    );

    if (!statusFilter || !applyButton) {
        console.error("Authority complaint filter elements not found.");
        return;
    }

    statusFilter.value = status;

    document.querySelectorAll(".quick-filter").forEach(button => {
        button.classList.remove("active");
    });

    const selectedButton = Array.from(
        document.querySelectorAll(".quick-filter")
    ).find(button =>
        button.getAttribute("onclick") ===
        `filterAuthorityComplaints('${status}')`
    );

    if (selectedButton) {
        selectedButton.classList.add("active");
    }

    applyButton.click();
}