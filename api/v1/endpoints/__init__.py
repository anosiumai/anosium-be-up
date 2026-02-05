"""
API v1 Endpoints Package
"""
from fastapi import APIRouter

# Import all endpoint routers
from .auth import router as auth_router
from .tenants import router as tenants_router
from .users import router as users_router
from .patients import router as patients_router
from .doctors import router as doctors_router
from .departments import router as departments_router
from .appointments import router as appointments_router
from .visits import router as visits_router
from .services import router as services_router
from .billing import router as billing_router
from .ai_leads import router as ai_leads_router
from .notifications import router as notifications_router
from .analytics import router as analytics_router

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(patients_router, prefix="/patients", tags=["Patients"])
api_router.include_router(doctors_router, prefix="/doctors", tags=["Doctors"])
api_router.include_router(departments_router, prefix="/departments", tags=["Departments"])
api_router.include_router(appointments_router, prefix="/appointments", tags=["Appointments"])
api_router.include_router(visits_router, prefix="/visits", tags=["Visits"])
api_router.include_router(services_router, prefix="/services", tags=["Services & Packages"])
api_router.include_router(billing_router, prefix="/billing", tags=["Billing & Payments"])
api_router.include_router(ai_leads_router, prefix="/ai-leads", tags=["AI Leads"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics & Reports"])

# Export
__all__ = ["api_router"]
