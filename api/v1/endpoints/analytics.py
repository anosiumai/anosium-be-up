from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime, timedelta

from app.api import deps
from app.schemas.analytics import (
    DashboardStats, DailyMetrics, RevenueReport,
    AppointmentReport, PatientReport
)
from app.services.analytics_service import AnalyticsService
from app.models.user import User, UserRole
from app.models.tenant import Tenant

router = APIRouter()

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(deps.get_current_user),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get dashboard statistics and metrics
    
    **Includes:**
    - Today's appointments and revenue
    - Pending payments
    - Active patients and doctors
    - New leads
    - Top services
    - Recent activity
    """
    service = AnalyticsService(db, current_tenant.id)
    
    stats = service.get_dashboard_stats()
    return stats

@router.get("/metrics/daily", response_model=DailyMetrics)
async def get_daily_metrics(
    metric_date: date = Query(default_factory=date.today),
    current_user: User = Depends(deps.require_role([UserRole.ACCOUNTANT, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get detailed metrics for a specific date
    
    **Required Permissions:** Accountant, Clinic Admin, or Super Admin
    """
    service = AnalyticsService(db, current_tenant.id)
    
    metrics = service.get_daily_metrics(metric_date)
    
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics not found for this date"
        )
    
    return metrics

@router.get("/reports/revenue", response_model=RevenueReport)
async def get_revenue_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    current_user: User = Depends(deps.require_role([UserRole.ACCOUNTANT, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN])),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get revenue report for date range
    
    **Required Permissions:** Accountant, Clinic Admin, or Super Admin
    
    **Includes:**
    - Total invoiced, collected, and pending
    - Payment methods breakdown
    - Daily revenue breakdown
    - Top revenue-generating services
    """
    if (to_date - from_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days"
        )
    
    service = AnalyticsService(db, current_tenant.id)
    
    report = service.get_revenue_report(from_date, to_date)
    return report

@router.get("/reports/appointments", response_model=AppointmentReport)
async def get_appointment_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get appointment analytics report
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Includes:**
    - Total scheduled, completed, cancelled
    - Breakdown by doctor, type, status
    - Peak hours analysis
    """
    if (to_date - from_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days"
        )
    
    service = AnalyticsService(db, current_tenant.id)
    
    report = service.get_appointment_report(from_date, to_date)
    return report

@router.get("/reports/patients", response_model=PatientReport)
async def get_patient_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get patient analytics report
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Includes:**
    - New registrations
    - Total active patients
    - Demographics breakdown
    - Visit frequency
    - Top conditions
    """
    if (to_date - from_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days"
        )
    
    service = AnalyticsService(db, current_tenant.id)
    
    report = service.get_patient_report(from_date, to_date)
    return report

@router.get("/trends/monthly")
async def get_monthly_trends(
    months: int = Query(6, ge=1, le=24),
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get monthly trends for key metrics
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Returns:**
    - Revenue trends
    - Appointment trends
    - Patient growth trends
    """
    service = AnalyticsService(db, current_tenant.id)
    
    trends = service.get_monthly_trends(months)
    return trends

@router.get("/performance/doctors")
async def get_doctor_performance(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user: User = Depends(deps.require_clinic_admin),
    current_tenant: Tenant = Depends(deps.get_current_tenant),
    db: Session = Depends(deps.get_db)
):
    """
    Get doctor performance metrics
    
    **Required Permissions:** Clinic Admin or Super Admin
    
    **Includes:**
    - Appointments handled
    - Revenue generated
    - Patient satisfaction
    - Average consultation time
    """
    service = AnalyticsService(db, current_tenant.id)
    
    performance = service.get_doctor_performance(from_date, to_date)
    return performance