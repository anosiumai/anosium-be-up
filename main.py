"""
API v1 Router - Aggregates all endpoint routers
"""

from fastapi import APIRouter

from api.v1.endpoints import (
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
)

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

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
    tags=["Services & Packages"]
)

api_router.include_router(
    billing.router,
    prefix="/billing",
    tags=["Billing & Payments"]
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
    tags=["Analytics & Reports"]
)