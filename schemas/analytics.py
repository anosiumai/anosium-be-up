from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
from datetime import date, datetime

class DailyMetricsInDB(BaseModel):
    """Daily metrics from database"""
    id: int
    tenant_id: int
    metric_date: date
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    new_patients: int
    returning_patients: int
    total_revenue: int
    paid_revenue: int
    pending_revenue: int
    ai_leads_captured: int
    ai_leads_converted: int
    ai_bookings: int
    average_wait_time_minutes: Optional[float]
    average_consultation_time_minutes: Optional[float]
    metrics_json: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

class DailyMetrics(DailyMetricsInDB):
    """Public daily metrics schema"""
    completion_rate: float = 0.0
    cancellation_rate: float = 0.0
    no_show_rate: float = 0.0
    revenue_collection_rate: float = 0.0
    ai_conversion_rate: float = 0.0
    
    @validator('completion_rate', pre=True, always=True)
    def calc_completion_rate(cls, v, values):
        total = values.get('total_appointments', 0)
        completed = values.get('completed_appointments', 0)
        return round((completed / total * 100) if total > 0 else 0, 2)
    
    @validator('cancellation_rate', pre=True, always=True)
    def calc_cancellation_rate(cls, v, values):
        total = values.get('total_appointments', 0)
        cancelled = values.get('cancelled_appointments', 0)
        return round((cancelled / total * 100) if total > 0 else 0, 2)

class DashboardStats(BaseModel):
    """Dashboard statistics"""
    today_appointments: int = 0
    today_revenue: int = 0
    pending_payments: int = 0
    active_patients: int = 0
    total_doctors: int = 0
    new_leads_today: int = 0
    appointments_this_week: int = 0
    revenue_this_month: int = 0
    top_services: List[Dict[str, Any]] = []
    recent_activity: List[Dict[str, Any]] = []

class RevenueReport(BaseModel):
    """Revenue report"""
    period_start: date
    period_end: date
    total_invoiced: int
    total_collected: int
    total_pending: int
    total_discounts: int
    payment_methods: Dict[str, int]
    daily_breakdown: List[Dict[str, Any]]
    top_revenue_services: List[Dict[str, Any]]

class AppointmentReport(BaseModel):
    """Appointment report"""
    period_start: date
    period_end: date
    total_scheduled: int
    completed: int
    cancelled: int
    no_shows: int
    rescheduled: int
    by_doctor: List[Dict[str, Any]]
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    peak_hours: List[Dict[str, Any]]

class PatientReport(BaseModel):
    """Patient report"""
    period_start: date
    period_end: date
    new_registrations: int
    total_active: int
    total_visits: int
    average_visits_per_patient: float
    by_age_group: Dict[str, int]
    by_gender: Dict[str, int]
    top_conditions: List[Dict[str, Any]]