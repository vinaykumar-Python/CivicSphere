import os
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from pathlib import Path
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.routes import router
from app.profile_routes import router as profile_router
from app.database import Base, check_database_connection, engine
from app import models

from app.analytics_routes import router as analytics_router
from app.complaint_routes import router as complaint_router
from app.authority_routes import router as authority_router
from app.history_routes import router as history_router
from app.dashboard_routes import router as dashboard_router
from app.authority_dashboard_routes import router as authority_dashboard_router
from app.citizen_analytics_routes import router as citizen_analytics_router
from app.category_routes import router as category_router

from app.ml_routes import router as ml_router
from app.weather_routes import router as weather_router
from app.risk_routes import router as risk_router
from app.notification_routes import router as notification_router

from app.sla_service import (
    process_sla_escalations,
    CHECK_INTERVAL_MINUTES,
)


# --------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------

DEFAULT_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5501",
    "http://localhost:5501",
]

configured_origins = os.getenv("CORS_ORIGINS")

if configured_origins:
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
else:
    ALLOWED_ORIGINS = DEFAULT_ORIGINS


# --------------------------------------------------
# SLA SCHEDULER
# --------------------------------------------------

sla_scheduler = BackgroundScheduler(
    timezone="Asia/Kolkata"
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Development-only automatic table creation.
    # Production should use database migrations.
    if os.getenv("APP_ENV", "development").lower() == "development":
        Base.metadata.create_all(bind=engine)

    # Start the SLA scheduler in development/single-worker mode.
    if (
    os.getenv("APP_ENV", "development").lower() == "development"
    and os.getenv("ENABLE_SLA_SCHEDULER", "true").lower() == "true"
    and not sla_scheduler.running
):
        sla_scheduler.add_job(
            process_sla_escalations,
            trigger="interval",
            minutes=CHECK_INTERVAL_MINUTES,
            id="sla_escalation_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        sla_scheduler.start()
        print("CivicCare AI: SLA scheduler started.")

    try:
        yield
    finally:
        if sla_scheduler.running:
            sla_scheduler.shutdown(wait=False)
            print("CivicCare AI: SLA scheduler stopped.")


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="CivicCare AI",
    description="AI-Powered Civic Complaint & Urban Risk Intelligence Platform",
    version="0.2.0",
    lifespan=lifespan,
)

# --------------------------------------------------
# APPLICATION LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("civiccare")


# --------------------------------------------------
# CENTRALIZED ERROR HANDLING
# --------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled application error on %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected server error occurred. Please try again later."
        },
    )
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(self)"
    )

    return response
# --------------------------------------------------
# CORS MIDDLEWARE
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# --------------------------------------------------
# API ROUTERS
# --------------------------------------------------

app.include_router(router)
app.include_router(profile_router)
app.include_router(complaint_router)
app.include_router(authority_router)
app.include_router(history_router)
app.include_router(dashboard_router)
app.include_router(authority_dashboard_router)
app.include_router(analytics_router)
app.include_router(citizen_analytics_router)
app.include_router(category_router)
app.include_router(ml_router)
app.include_router(weather_router)
app.include_router(risk_router)
app.include_router(notification_router)


# --------------------------------------------------
# HEALTH CHECKS
# --------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "CivicCare AI",
    }


@app.get("/api/health/database")
def database_health():

    try:
        check_database_connection()

        return {
            "status": "connected",
            "service": "database",
        }

    except Exception:
        logger.exception("Database health check failed.")

    raise HTTPException(
        status_code=503,
        detail="Database connection failed.",
    ) from None


# --------------------------------------------------
# FRONTEND
# --------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend",
)