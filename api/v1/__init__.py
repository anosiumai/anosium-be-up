from fastapi import APIRouter
from .endpoints import (
    auth,
    tenants,
    users,
    patients,
    doctors,
    departments,
    appointments,
    visits,
    services,
    billing,
    ai_leads,
    notifications,
    analytics,
    admin,
)

api_router = APIRouter()

# Public endpoints (no auth required)
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Protected endpoints (auth required)
api_router.include_router(
    tenants.router,
    prefix="/tenants",
    tags=["Tenants"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

api_router.include_router(
    patients.router,
    prefix="/patients",
    tags=["Patients"]
)

api_router.include_router(
    doctors.router,
    prefix="/doctors",
    tags=["Doctors"]
)

api_router.include_router(
    departments.router,
    prefix="/departments",
    tags=["Departments"]
)

api_router.include_router(
    appointments.router,
    prefix="/appointments",
    tags=["Appointments"]
)

api_router.include_router(
    visits.router,
    prefix="/visits",
    tags=["Visits"]
)

api_router.include_router(
    services.router,
    prefix="/services",
    tags=["Services"]
)

api_router.include_router(
    billing.router,
    prefix="/billing",
    tags=["Billing"]
)

api_router.include_router(
    ai_leads.router,
    prefix="/ai-leads",
    tags=["AI Leads"]
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"]
)

__all__ = ["api_router"]