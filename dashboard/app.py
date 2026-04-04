"""
Toolkit LLM Gateway - Analytics Dashboard

FastAPI application serving the analytics dashboard UI and API endpoints.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from toolkit_extensions import __version__
from toolkit_extensions.alert_webhooks import AlertWebhookManager
from toolkit_extensions.budget_manager import BudgetManager
from toolkit_extensions.cost_analytics import CostAnalytics, TimeGranularity
from toolkit_extensions.database.connection import DatabaseConfig, init_database
from toolkit_extensions.health_check import create_health_checker

# ---------------------------------------------------------------------------
# API Key Authentication
# ---------------------------------------------------------------------------
# Set DASHBOARD_API_KEY env var to require authentication on /api/* endpoints.
# If not set, a warning is logged and the dashboard runs without auth (dev mode).
# ---------------------------------------------------------------------------
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY")

if not DASHBOARD_API_KEY:
    logger.warning(
        "DASHBOARD_API_KEY is not set. Dashboard API endpoints are unauthenticated. "
        "Set DASHBOARD_API_KEY env var for production use."
    )

# Paths that do not require authentication
_PUBLIC_PATHS = frozenset({"/", "/health", "/docs", "/openapi.json", "/redoc"})


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid API key for /api/* endpoints when DASHBOARD_API_KEY is set."""

    async def dispatch(self, request: Request, call_next):
        if DASHBOARD_API_KEY and request.url.path.startswith("/api/"):
            # Only accept API key via header to prevent credential leakage in
            # access logs and browser history.
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key != DASHBOARD_API_KEY:
                logger.warning("Rejected unauthenticated request to %s", request.url.path)
                return JSONResponse(
                    {"success": False, "error": "Invalid or missing API key"},
                    status_code=401,
                )
        return await call_next(request)


# Initialize FastAPI app
app = FastAPI(
    title="Toolkit LLM Gateway Dashboard",
    description="Analytics dashboard for LLM cost tracking and budgets",
    version="1.0.0",
)

# Add API key auth middleware
app.add_middleware(APIKeyAuthMiddleware)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
templates = Jinja2Templates(directory="dashboard/templates")

# Initialize database and components
db_config = DatabaseConfig()
db_manager = init_database(db_config)

analytics = CostAnalytics()
budget_manager = BudgetManager()
webhook_manager = AlertWebhookManager()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/summary")
async def get_summary(days: int = 30):
    """
    Get cost summary for the specified number of days

    Args:
        days: Number of days to look back (default: 30)
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        summary = analytics.get_summary(start_date=start_date)

        return JSONResponse({"success": True, "data": summary})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/cost-by-model")
async def get_cost_by_model(limit: int = 10):
    """Get top models by cost"""
    try:
        data = analytics.get_cost_by_model(limit=limit)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/cost-by-user")
async def get_cost_by_user(limit: int = 10):
    """Get top users by cost"""
    try:
        data = analytics.get_cost_by_user(limit=limit)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/cost-by-team")
async def get_cost_by_team(limit: int = 10):
    """Get top teams by cost"""
    try:
        data = analytics.get_cost_by_team(limit=limit)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/time-series")
async def get_time_series(granularity: str = "daily", days: int = 7):
    """
    Get time-series cost data

    Args:
        granularity: hourly, daily, weekly, monthly
        days: Number of days to look back
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Map string to enum
        granularity_map = {
            "hourly": TimeGranularity.HOURLY,
            "daily": TimeGranularity.DAILY,
            "weekly": TimeGranularity.WEEKLY,
            "monthly": TimeGranularity.MONTHLY,
        }

        gran = granularity_map.get(granularity.lower(), TimeGranularity.DAILY)
        data = analytics.get_time_series(granularity=gran, start_date=start_date)

        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/performance")
async def get_performance():
    """Get performance statistics"""
    try:
        stats = analytics.get_performance_stats()
        return JSONResponse({"success": True, "data": stats})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/budgets")
async def get_budgets():
    """Get all active budgets"""
    try:
        # Get all budgets (this is a simplified version)
        # In production, you'd want pagination and filtering
        return JSONResponse(
            {
                "success": True,
                "data": [],  # TODO: Implement get_all_budgets method
            }
        )
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/webhooks")
async def get_webhooks():
    """Get all webhooks with delivery stats"""
    try:
        webhooks = webhook_manager.get_webhooks()

        # Add delivery stats to each webhook
        for webhook in webhooks:
            stats = webhook_manager.get_delivery_stats(webhook["id"])
            webhook["stats"] = stats

        return JSONResponse({"success": True, "data": webhooks})
    except Exception as e:
        logger.exception("API error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/version")
async def version():
    """Return the toolkit-llm-gateway version"""
    return JSONResponse(
        {
            "version": __version__,
            "name": "toolkit-llm-gateway",
        }
    )


@app.get("/health")
async def health_check(detailed: bool = False):
    """Health check endpoint with optional dependency status"""
    checker = create_health_checker(db_manager=db_manager)
    result = checker.check_health(detailed=detailed)
    status_code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(result, status_code=status_code)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=12000, log_level="info")
