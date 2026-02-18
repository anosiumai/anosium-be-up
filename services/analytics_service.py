"""
Analytics Service - CORRECTED VERSION
Handles all analytics, reporting, and metrics calculations for the healthcare management system
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, extract
from datetime import date, datetime, timedelta
from collections import defaultdict

from models.analytics import DailyMetrics
from models.appointment import Appointment, AppointmentStatus
from models.patient import Patient
from models.doctor import Doctor
from models.user import User
from models.visit import Visit
from models.billing import Invoice, Payment, PaymentMethod, InvoiceItem
from models.service import Service
from models.ai_lead import AILead
from repositories.analytics import DailyMetricsRepository
from schemas.analytics import (
    DashboardStats, DailyMetrics as DailyMetricsSchema,
    RevenueReport, AppointmentReport, PatientReport
)


class AnalyticsService:
    """Service for analytics and reporting operations"""
    
    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.metrics_repo = DailyMetricsRepository(db, tenant_id)
    
    # ============================================================================
    # DASHBOARD STATISTICS
    # ============================================================================
    
    def get_dashboard_stats(self) -> DashboardStats:
        """
        Get comprehensive dashboard statistics
        Returns real-time metrics for today and summary metrics
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Today's appointments
        today_appointments = self._count_appointments_by_date(today)
        
        # Today's revenue (from completed visits/invoices)
        today_revenue = self._get_revenue_by_date(today)
        
        # Pending payments (all unpaid invoices)
        pending_payments = self._get_pending_payments()
        
        # Active patients (patients with at least one visit in last 90 days)
        active_patients = self._count_active_patients()
        recently_active_patients = self._count_recently_active_patients(days=90)
        
        # Total active doctors
        total_doctors = self._count_active_doctors()
        
        # New leads today
        new_leads_today = self._count_leads_by_date(today)
        
        # This week's appointments
        appointments_this_week = self._count_appointments_date_range(
            week_start, today
        )
        
        # This month's revenue
        revenue_this_month = self._get_revenue_date_range(
            month_start, today
        )
        
        # Top services (by revenue/frequency in last 30 days)
        top_services = self._get_top_services(days=30, limit=5)
        
        # Recent activity (last 10 activities)
        recent_activity = self._get_recent_activity(limit=10)
        
        return DashboardStats(
            today_appointments=today_appointments,
            today_revenue=today_revenue,
            pending_payments=pending_payments,
            active_patients=active_patients,
            recently_active_patients=recently_active_patients,
            total_doctors=total_doctors,
            new_leads_today=new_leads_today,
            appointments_this_week=appointments_this_week,
            revenue_this_month=revenue_this_month,
            top_services=top_services,
            recent_activity=recent_activity
        )
    
    # ============================================================================
    # DAILY METRICS
    # ============================================================================
    
    def get_daily_metrics(self, metric_date: date) -> Optional[DailyMetricsSchema]:
        """Get or calculate daily metrics for a specific date"""
        # Try to get from database first
        metrics = self.metrics_repo.get_by_date(metric_date)
        
        if not metrics:
            # Calculate and store metrics if not exists
            metrics = self._calculate_and_store_daily_metrics(metric_date)
        
        if metrics:
            return DailyMetricsSchema.from_orm(metrics)
        
        return None
    
    def _calculate_and_store_daily_metrics(self, metric_date: date) -> Optional[DailyMetrics]:
        """Calculate and store daily metrics"""
        # Get appointment stats
        appointment_stats = self._get_appointment_stats_for_date(metric_date)
        
        # Get patient stats
        patient_stats = self._get_patient_stats_for_date(metric_date)
        
        # Get revenue stats
        revenue_stats = self._get_revenue_stats_for_date(metric_date)
        
        # Get AI lead stats
        ai_stats = self._get_ai_stats_for_date(metric_date)
        
        # Get performance metrics
        performance = self._get_performance_metrics_for_date(metric_date)
        
        # Create metrics record
        metrics = DailyMetrics(
            tenant_id=self.tenant_id,
            metric_date=metric_date,
            total_appointments=appointment_stats['total'],
            completed_appointments=appointment_stats['completed'],
            cancelled_appointments=appointment_stats['cancelled'],
            no_show_appointments=appointment_stats['no_show'],
            new_patients=patient_stats['new'],
            returning_patients=patient_stats['returning'],
            total_revenue=revenue_stats['total'],
            paid_revenue=revenue_stats['paid'],
            pending_revenue=revenue_stats['pending'],
            ai_leads_captured=ai_stats['captured'],
            ai_leads_converted=ai_stats['converted'],
            ai_bookings=ai_stats['bookings'],
            average_wait_time_minutes=performance.get('avg_wait_time'),
            average_consultation_time_minutes=performance.get('avg_consultation_time'),
            metrics_json={}
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    # ============================================================================
    # REPORTS
    # ============================================================================
    
    def get_revenue_report(
        self,
        from_date: date,
        to_date: date
    ) -> RevenueReport:
        """Generate comprehensive revenue report"""
        # Total invoiced
        total_invoiced = self._get_total_invoiced(from_date, to_date)
        
        # Total collected
        total_collected = self._get_total_collected(from_date, to_date)
        
        # Total pending
        total_pending = self._get_total_pending(from_date, to_date)
        
        # Total discounts
        total_discounts = self._get_total_discounts(from_date, to_date)
        
        # Payment methods breakdown
        payment_methods = self._get_payment_methods_breakdown(from_date, to_date)
        
        # Daily breakdown
        daily_breakdown = self._get_daily_revenue_breakdown(from_date, to_date)
        
        # Top revenue-generating services
        top_revenue_services = self._get_top_revenue_services(from_date, to_date, limit=10)
        
        return RevenueReport(
            period_start=from_date,
            period_end=to_date,
            total_invoiced=total_invoiced,
            total_collected=total_collected,
            total_pending=total_pending,
            total_discounts=total_discounts,
            payment_methods=payment_methods,
            daily_breakdown=daily_breakdown,
            top_revenue_services=top_revenue_services
        )
    
    def get_appointment_report(
        self,
        from_date: date,
        to_date: date
    ) -> AppointmentReport:
        """Generate comprehensive appointment report"""
        # Get all appointments in range
        appointments_query = (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
        )
        
        all_appointments = appointments_query.all()
        
        # Calculate totals
        total_scheduled = len(all_appointments)
        completed = sum(1 for a in all_appointments if a.status == AppointmentStatus.COMPLETED)
        cancelled = sum(1 for a in all_appointments if a.status == AppointmentStatus.CANCELLED)
        no_shows = sum(1 for a in all_appointments if a.status == AppointmentStatus.NO_SHOW)
        # FIX: Changed from rescheduled_from_id to status check
        rescheduled = sum(1 for a in all_appointments if a.status == AppointmentStatus.RESCHEDULED)
        
        # By doctor
        by_doctor = self._get_appointments_by_doctor(from_date, to_date)
        
        # By type
        by_type = self._get_appointments_by_type(from_date, to_date)
        
        # By status
        by_status = self._get_appointments_by_status(from_date, to_date)
        
        # Peak hours
        peak_hours = self._get_peak_appointment_hours(from_date, to_date)
        
        return AppointmentReport(
            period_start=from_date,
            period_end=to_date,
            total_scheduled=total_scheduled,
            completed=completed,
            cancelled=cancelled,
            no_shows=no_shows,
            rescheduled=rescheduled,
            by_doctor=by_doctor,
            by_type=by_type,
            by_status=by_status,
            peak_hours=peak_hours
        )
    
    def get_patient_report(
        self,
        from_date: date,
        to_date: date
    ) -> PatientReport:
        """Generate comprehensive patient report"""
        # New registrations
        new_registrations = (
            self.db.query(func.count(Patient.id))
            .filter(
                and_(
                    Patient.tenant_id == self.tenant_id,
                    Patient.created_at >= from_date,
                    Patient.created_at <= to_date
                )
            )
            .scalar() or 0
        )
        
        # Total active patients (those with visits in period)
        total_active = (
            self.db.query(func.count(func.distinct(Visit.patient_id)))
            .filter(
                and_(
                    Visit.tenant_id == self.tenant_id,
                    Visit.visit_date >= from_date,
                    Visit.visit_date <= to_date
                )
            )
            .scalar() or 0
        )
        
        # Total visits
        total_visits = (
            self.db.query(func.count(Visit.id))
            .filter(
                and_(
                    Visit.tenant_id == self.tenant_id,
                    Visit.visit_date >= from_date,
                    Visit.visit_date <= to_date
                )
            )
            .scalar() or 0
        )
        
        # Average visits per patient
        average_visits_per_patient = (
            round(total_visits / total_active, 2) if total_active > 0 else 0.0
        )
        
        # Demographics
        by_age_group = self._get_patients_by_age_group(from_date, to_date)
        by_gender = self._get_patients_by_gender(from_date, to_date)
        
        # Top conditions
        top_conditions = self._get_top_conditions(from_date, to_date, limit=10)
        
        return PatientReport(
            period_start=from_date,
            period_end=to_date,
            new_registrations=new_registrations,
            total_active=total_active,
            total_visits=total_visits,
            average_visits_per_patient=average_visits_per_patient,
            by_age_group=by_age_group,
            by_gender=by_gender,
            top_conditions=top_conditions
        )
    
    # ============================================================================
    # TRENDS AND PERFORMANCE
    # ============================================================================
    
    def get_monthly_trends(self, months: int = 6) -> Dict[str, Any]:
        """Get monthly trends for key metrics"""
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        # Get monthly aggregated data
        revenue_trend = self._get_monthly_revenue_trend(start_date, end_date)
        appointment_trend = self._get_monthly_appointment_trend(start_date, end_date)
        patient_trend = self._get_monthly_patient_growth(start_date, end_date)
        
        return {
            'revenue_trend': revenue_trend,
            'appointment_trend': appointment_trend,
            'patient_trend': patient_trend,
            'period_months': months,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
    
    def get_doctor_performance(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get performance metrics for all doctors"""
        if not from_date:
            from_date = date.today() - timedelta(days=30)
        if not to_date:
            to_date = date.today()
        
        doctors = (
            self.db.query(Doctor)
            .join(User, User.id == Doctor.user_id)
            .filter(
                and_(
                    Doctor.tenant_id == self.tenant_id,
                    Doctor.is_active == True
                )
            )
            .all()
        )
        
        performance_data = []
        
        for doctor in doctors:
            # Get doctor's appointments
            appointments = (
                self.db.query(Appointment)
                .filter(
                    and_(
                        Appointment.tenant_id == self.tenant_id,
                        Appointment.doctor_id == doctor.id,
                        Appointment.appointment_date >= from_date,
                        Appointment.appointment_date <= to_date
                    )
                )
                .all()
            )
            
            total_appointments = len(appointments)
            completed_appointments = sum(
                1 for a in appointments if a.status == AppointmentStatus.COMPLETED
            )
            
            # Get revenue generated
            revenue = (
                self.db.query(func.sum(Invoice.total_amount))
                .join(Visit, Visit.id == Invoice.visit_id)
                .filter(
                    and_(
                        Invoice.tenant_id == self.tenant_id,
                        Visit.doctor_id == doctor.id,
                        Visit.visit_date >= from_date,
                        Visit.visit_date <= to_date
                    )
                )
                .scalar() or 0
            )
            
            # Calculate average consultation time
            avg_consultation_time = self._get_avg_consultation_time_for_doctor(
                doctor.id, from_date, to_date
            )
            
            # Patient satisfaction (if feedback system exists)
            patient_satisfaction = None  # Placeholder
            
            # FIX: Access doctor name through user relationship
            performance_data.append({
                'doctor_id': doctor.id,
                'doctor_name': f"{doctor.user.first_name} {doctor.user.last_name}",
                'specialization': doctor.specialization,
                'total_appointments': total_appointments,
                'completed_appointments': completed_appointments,
                'completion_rate': round(
                    (completed_appointments / total_appointments * 100)
                    if total_appointments > 0 else 0, 2
                ),
                'revenue_generated': revenue,
                'average_consultation_time_minutes': avg_consultation_time,
                'patient_satisfaction': patient_satisfaction
            })
        
        # Sort by revenue
        performance_data.sort(key=lambda x: x['revenue_generated'], reverse=True)
        
        return performance_data
    
    # ============================================================================
    # HELPER METHODS - BASIC QUERIES
    # ============================================================================
    
    def _count_appointments_by_date(self, target_date: date) -> int:
        """Count appointments for a specific date"""
        return (
            self.db.query(func.count(Appointment.id))
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date == target_date
                )
            )
            .scalar() or 0
        )
    
    def _count_appointments_date_range(self, from_date: date, to_date: date) -> int:
        """Count appointments in date range"""
        return (
            self.db.query(func.count(Appointment.id))
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .scalar() or 0
        )
    
    def _get_revenue_by_date(self, target_date: date) -> int:
        """Get total revenue for a specific date (in cents)"""
        return (
            self.db.query(func.sum(Payment.amount))
            .filter(
                and_(
                    Payment.tenant_id == self.tenant_id,
                    func.date(Payment.payment_date) == target_date
                )
            )
            .scalar() or 0
        )
    
    def _get_revenue_date_range(self, from_date: date, to_date: date) -> int:
        """Get total revenue for date range (in cents)"""
        return (
            self.db.query(func.sum(Payment.amount))
            .filter(
                and_(
                    Payment.tenant_id == self.tenant_id,
                    func.date(Payment.payment_date) >= from_date,
                    func.date(Payment.payment_date) <= to_date
                )
            )
            .scalar() or 0
        )
    
    def _get_pending_payments(self) -> int:
        """Get total pending payment amount (in cents)"""
        return (
            self.db.query(func.sum(Invoice.total_amount - Invoice.paid_amount))
            .filter(
                and_(
                    Invoice.tenant_id == self.tenant_id,
                    Invoice.paid_amount < Invoice.total_amount
                )
            )
            .scalar() or 0
        )
    
    def _count_active_patients(self, days: int = 90) -> int:
        """Count all registered active patients for this tenant"""
        return (
            self.db.query(func.count(Patient.id))
            .filter(
                and_(
                    Patient.tenant_id == self.tenant_id,
                    Patient.is_active == True
                )
            )
            .scalar() or 0
        )

    def _count_recently_active_patients(self, days: int = 90) -> int:
        """Count patients with at least one visit in last N days"""
        cutoff_date = date.today() - timedelta(days=days)
        return (
            self.db.query(func.count(func.distinct(Visit.patient_id)))
            .filter(
                and_(
                    Visit.tenant_id == self.tenant_id,
                    Visit.visit_date >= cutoff_date
                )
            )
            .scalar() or 0
        )
    
    def _count_active_doctors(self) -> int:
        """Count active doctors"""
        return (
            self.db.query(func.count(Doctor.id))
            .filter(
                and_(
                    Doctor.tenant_id == self.tenant_id,
                    Doctor.is_active == True
                )
            )
            .scalar() or 0
        )
    
    def _count_leads_by_date(self, target_date: date) -> int:
        """Count AI leads created on a specific date"""
        return (
            self.db.query(func.count(AILead.id))
            .filter(
                and_(
                    AILead.tenant_id == self.tenant_id,
                    func.date(AILead.created_at) == target_date
                )
            )
            .scalar() or 0
        )
    
    # ============================================================================
    # HELPER METHODS - STATISTICS
    # ============================================================================
    
    def _get_appointment_stats_for_date(self, target_date: date) -> Dict[str, int]:
        """Get appointment statistics for a specific date"""
        appointments = (
            self.db.query(Appointment)
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date == target_date
                )
            )
            .all()
        )
        
        return {
            'total': len(appointments),
            'completed': sum(1 for a in appointments if a.status == AppointmentStatus.COMPLETED),
            'cancelled': sum(1 for a in appointments if a.status == AppointmentStatus.CANCELLED),
            'no_show': sum(1 for a in appointments if a.status == AppointmentStatus.NO_SHOW)
        }
    
    def _get_patient_stats_for_date(self, target_date: date) -> Dict[str, int]:
        """Get patient statistics for a specific date"""
        # New patients registered on this date
        new_patients = (
            self.db.query(func.count(Patient.id))
            .filter(
                and_(
                    Patient.tenant_id == self.tenant_id,
                    func.date(Patient.created_at) == target_date
                )
            )
            .scalar() or 0
        )
        
        # Returning patients (had visits before this date)
        visits_on_date = (
            self.db.query(Visit.patient_id)
            .filter(
                and_(
                    Visit.tenant_id == self.tenant_id,
                    Visit.visit_date == target_date
                )
            )
            .distinct()
            .all()
        )
        
        returning = 0
        for (patient_id,) in visits_on_date:
            previous_visits = (
                self.db.query(func.count(Visit.id))
                .filter(
                    and_(
                        Visit.tenant_id == self.tenant_id,
                        Visit.patient_id == patient_id,
                        Visit.visit_date < target_date
                    )
                )
                .scalar() or 0
            )
            if previous_visits > 0:
                returning += 1
        
        return {
            'new': new_patients,
            'returning': returning
        }
    
    def _get_revenue_stats_for_date(self, target_date: date) -> Dict[str, int]:
        """Get revenue statistics for a specific date"""
        # Invoices created on this date
        invoices = (
            self.db.query(Invoice)
            .filter(
                and_(
                    Invoice.tenant_id == self.tenant_id,
                    func.date(Invoice.created_at) == target_date
                )
            )
            .all()
        )
        
        total = sum(inv.total_amount for inv in invoices)
        paid = sum(inv.paid_amount for inv in invoices)
        pending = total - paid
        
        return {
            'total': total,
            'paid': paid,
            'pending': pending
        }
    
    def _get_ai_stats_for_date(self, target_date: date) -> Dict[str, int]:
        """Get AI lead statistics for a specific date"""
        leads = (
            self.db.query(AILead)
            .filter(
                and_(
                    AILead.tenant_id == self.tenant_id,
                    func.date(AILead.created_at) == target_date
                )
            )
            .all()
        )
        
        captured = len(leads)
        # FIX: Changed from converted_to_patient_id to patient_id
        converted = sum(1 for lead in leads if lead.patient_id is not None)
        
        # FIX: Query appointments instead of non-existent field
        bookings = (
            self.db.query(func.count(Appointment.id))
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.booked_via_ai == True,
                    func.date(Appointment.created_at) == target_date
                )
            )
            .scalar() or 0
        )
        
        return {
            'captured': captured,
            'converted': converted,
            'bookings': bookings
        }
    
    def _get_performance_metrics_for_date(self, target_date: date) -> Dict[str, Optional[float]]:
        """Get performance metrics for a specific date"""
        # This would require visit timing data
        # Placeholder for now - would need actual wait time and consultation time tracking
        
        return {
            'avg_wait_time': None,
            'avg_consultation_time': None
        }
    
    # ============================================================================
    # HELPER METHODS - TOP ITEMS AND BREAKDOWNS
    # ============================================================================
    
    def _get_top_services(self, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top services by usage and revenue
        FIX: Use InvoiceItem junction table instead of Visit.service_id
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        # Join through invoice_items to track services used
        services_data = (
            self.db.query(
                Service.id,
                Service.name,
                func.count(InvoiceItem.id).label('usage_count'),
                func.sum(InvoiceItem.total_amount).label('revenue')
            )
            .join(InvoiceItem, InvoiceItem.service_id == Service.id)
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
            .join(Visit, Visit.id == Invoice.visit_id)
            .filter(
                and_(
                    Service.tenant_id == self.tenant_id,
                    Visit.visit_date >= cutoff_date
                )
            )
            .group_by(Service.id, Service.name)
            .order_by(func.sum(InvoiceItem.total_amount).desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                'service_id': s.id,
                'service_name': s.name,
                'usage_count': s.usage_count,
                'revenue': s.revenue or 0
            }
            for s in services_data
        ]
    
    def _get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity items"""
        activities = []
        
        # Recent appointments
        recent_appointments = (
            self.db.query(Appointment)
            .filter(Appointment.tenant_id == self.tenant_id)
            .order_by(Appointment.created_at.desc())
            .limit(limit // 2)
            .all()
        )
        
        for apt in recent_appointments:
            activities.append({
                'type': 'appointment',
                'description': f"New appointment scheduled",
                'timestamp': apt.created_at.isoformat() if apt.created_at else None,
                'id': apt.id
            })
        
        # Recent payments
        recent_payments = (
            self.db.query(Payment)
            .filter(Payment.tenant_id == self.tenant_id)
            .order_by(Payment.payment_date.desc())
            .limit(limit // 2)
            .all()
        )
        
        for payment in recent_payments:
            activities.append({
                'type': 'payment',
                'description': f"Payment received",
                'amount': payment.amount,
                'timestamp': payment.payment_date.isoformat(),
                'id': payment.id
            })
        
        # Sort by timestamp
        activities = [a for a in activities if a['timestamp'] is not None]
        activities.sort(key=lambda x: x['timestamp'], reverse=True)

        
        return activities[:limit]
    
    # ============================================================================
    # HELPER METHODS - REVENUE REPORTS
    # ============================================================================
    
    def _get_total_invoiced(self, from_date: date, to_date: date) -> int:
        """Get total invoiced amount in period"""
        return (
            self.db.query(func.sum(Invoice.total_amount))
            .filter(
                and_(
                    Invoice.tenant_id == self.tenant_id,
                    func.date(Invoice.created_at) >= from_date,
                    func.date(Invoice.created_at) <= to_date
                )
            )
            .scalar() or 0
        )
    
    def _get_total_collected(self, from_date: date, to_date: date) -> int:
        """Get total collected amount in period"""
        return (
            self.db.query(func.sum(Payment.amount))
            .filter(
                and_(
                    Payment.tenant_id == self.tenant_id,
                    func.date(Payment.payment_date) >= from_date,
                    func.date(Payment.payment_date) <= to_date
                )
            )
            .scalar() or 0
        )
    
    def _get_total_pending(self, from_date: date, to_date: date) -> int:
        """Get total pending amount for invoices in period"""
        invoices = (
            self.db.query(Invoice)
            .filter(
                and_(
                    Invoice.tenant_id == self.tenant_id,
                    func.date(Invoice.created_at) >= from_date,
                    func.date(Invoice.created_at) <= to_date
                )
            )
            .all()
        )
        
        return sum(inv.total_amount - inv.paid_amount for inv in invoices)
    
    def _get_total_discounts(self, from_date: date, to_date: date) -> int:
        """Get total discounts given in period"""
        return (
            self.db.query(func.sum(Invoice.discount_amount))
            .filter(
                and_(
                    Invoice.tenant_id == self.tenant_id,
                    func.date(Invoice.created_at) >= from_date,
                    func.date(Invoice.created_at) <= to_date
                )
            )
            .scalar() or 0
        )
    
    def _get_payment_methods_breakdown(
        self,
        from_date: date,
        to_date: date
    ) -> Dict[str, int]:
        """Get breakdown of payments by method"""
        payments = (
            self.db.query(
                Payment.payment_method,
                func.sum(Payment.amount).label('total')
            )
            .filter(
                and_(
                    Payment.tenant_id == self.tenant_id,
                    func.date(Payment.payment_date) >= from_date,
                    func.date(Payment.payment_date) <= to_date
                )
            )
            .group_by(Payment.payment_method)
            .all()
        )
        
        return {
            str(method): total for method, total in payments
        }
    
    def _get_daily_revenue_breakdown(
        self,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """Get daily revenue breakdown"""
        daily_data = (
            self.db.query(
                func.date(Payment.payment_date).label('date'),
                func.sum(Payment.amount).label('revenue')
            )
            .filter(
                and_(
                    Payment.tenant_id == self.tenant_id,
                    func.date(Payment.payment_date) >= from_date,
                    func.date(Payment.payment_date) <= to_date
                )
            )
            .group_by(func.date(Payment.payment_date))
            .order_by(func.date(Payment.payment_date))
            .all()
        )
        
        return [
            {
                'date': d.date.isoformat(),
                'revenue': d.revenue
            }
            for d in daily_data
        ]
    
    def _get_top_revenue_services(
        self,
        from_date: date,
        to_date: date,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top revenue-generating services
        FIX: Use InvoiceItem junction table instead of Visit.service_id
        """
        services = (
            self.db.query(
                Service.id,
                Service.name,
                func.count(InvoiceItem.id).label('usage_count'),
                func.sum(InvoiceItem.total_amount).label('revenue')
            )
            .join(InvoiceItem, InvoiceItem.service_id == Service.id)
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
            .join(Visit, Visit.id == Invoice.visit_id)
            .filter(
                and_(
                    Service.tenant_id == self.tenant_id,
                    Visit.visit_date >= from_date,
                    Visit.visit_date <= to_date
                )
            )
            .group_by(Service.id, Service.name)
            .order_by(func.sum(InvoiceItem.total_amount).desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                'service_id': s.id,
                'service_name': s.name,
                'usage_count': s.usage_count,
                'total_revenue': s.revenue or 0
            }
            for s in services
        ]
    
    # ============================================================================
    # HELPER METHODS - APPOINTMENT REPORTS
    # ============================================================================
    
    def _get_appointments_by_doctor(
        self,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """
        Get appointment breakdown by doctor
        FIX: Join User table to access doctor names
        """
        data = (
            self.db.query(
                Doctor.id,
                User.first_name,
                User.last_name,
                func.count(Appointment.id).label('total_appointments'),
                func.sum(
                    case((Appointment.status == AppointmentStatus.COMPLETED, 1), else_=0)
                ).label('completed')
            )
            .join(User, User.id == Doctor.user_id)
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .filter(
                and_(
                    Doctor.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .group_by(Doctor.id, User.first_name, User.last_name)
            .all()
        )
        
        return [
            {
                'doctor_id': d.id,
                'doctor_name': f"{d.first_name} {d.last_name}",
                'total_appointments': d.total_appointments,
                'completed': d.completed
            }
            for d in data
        ]
    
    def _get_appointments_by_type(
        self,
        from_date: date,
        to_date: date
    ) -> Dict[str, int]:
        """Get appointment breakdown by type"""
        data = (
            self.db.query(
                Appointment.appointment_type,
                func.count(Appointment.id).label('count')
            )
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .group_by(Appointment.appointment_type)
            .all()
        )
        
        return {
            str(apt_type): count for apt_type, count in data
        }
    
    def _get_appointments_by_status(
        self,
        from_date: date,
        to_date: date
    ) -> Dict[str, int]:
        """Get appointment breakdown by status"""
        data = (
            self.db.query(
                Appointment.status,
                func.count(Appointment.id).label('count')
            )
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .group_by(Appointment.status)
            .all()
        )
        
        return {
            str(status): count for status, count in data
        }
    
    def _get_peak_appointment_hours(
        self,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """Get peak appointment hours"""
        data = (
            self.db.query(
                extract('hour', Appointment.appointment_time).label('hour'),
                func.count(Appointment.id).label('count')
            )
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .group_by(extract('hour', Appointment.appointment_time))
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
            .all()
        )
        
        return [
            {
                'hour': int(d.hour),
                'appointment_count': d.count
            }
            for d in data
        ]
    
    # ============================================================================
    # HELPER METHODS - PATIENT REPORTS
    # ============================================================================
    
    def _get_patients_by_age_group(
        self,
        from_date: date,
        to_date: date
    ) -> Dict[str, int]:
        """Get patient distribution by age group"""
        # Get patients who had visits in the period
        patients_with_visits = (
            self.db.query(Patient)
            .join(Visit, Visit.patient_id == Patient.id)
            .filter(
                and_(
                    Patient.tenant_id == self.tenant_id,
                    Visit.visit_date >= from_date,
                    Visit.visit_date <= to_date
                )
            )
            .distinct()
            .all()
        )
        
        age_groups = {
            '0-17': 0,
            '18-30': 0,
            '31-45': 0,
            '46-60': 0,
            '61+': 0
        }
        
        today = date.today()
        for patient in patients_with_visits:
            if patient.date_of_birth:
                age = (today - patient.date_of_birth).days // 365
                if age < 18:
                    age_groups['0-17'] += 1
                elif age <= 30:
                    age_groups['18-30'] += 1
                elif age <= 45:
                    age_groups['31-45'] += 1
                elif age <= 60:
                    age_groups['46-60'] += 1
                else:
                    age_groups['61+'] += 1
        
        return age_groups
    
    def _get_patients_by_gender(
        self,
        from_date: date,
        to_date: date
    ) -> Dict[str, int]:
        """Get patient distribution by gender"""
        data = (
            self.db.query(
                Patient.gender,
                func.count(func.distinct(Patient.id)).label('count')
            )
            .join(Visit, Visit.patient_id == Patient.id)
            .filter(
                and_(
                    Patient.tenant_id == self.tenant_id,
                    Visit.visit_date >= from_date,
                    Visit.visit_date <= to_date
                )
            )
            .group_by(Patient.gender)
            .all()
        )
        
        return {
            str(gender or 'Unknown'): count for gender, count in data
        }
    
    def _get_top_conditions(
        self,
        from_date: date,
        to_date: date,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top diagnosed conditions"""
        # This assumes there's a diagnosis field or diagnosis table
        # Placeholder implementation
        
        # You would typically join with a diagnoses table
        # For now, returning empty list
        
        return []
    
    # ============================================================================
    # HELPER METHODS - TRENDS
    # ============================================================================
    
    def _get_monthly_revenue_trend(
        self,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """Get monthly revenue trend"""
        data = (
            self.db.query(
                extract('year', Payment.payment_date).label('year'),
                extract('month', Payment.payment_date).label('month'),
                func.sum(Payment.amount).label('revenue')
            )
            .filter(
                and_(
                    Payment.tenant_id == self.tenant_id,
                    func.date(Payment.payment_date) >= from_date,
                    func.date(Payment.payment_date) <= to_date
                )
            )
            .group_by(
                extract('year', Payment.payment_date),
                extract('month', Payment.payment_date)
            )
            .order_by(
                extract('year', Payment.payment_date),
                extract('month', Payment.payment_date)
            )
            .all()
        )
        
        return [
            {
                'year': int(d.year),
                'month': int(d.month),
                'revenue': d.revenue
            }
            for d in data
        ]
    
    def _get_monthly_appointment_trend(
        self,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """Get monthly appointment trend"""
        data = (
            self.db.query(
                extract('year', Appointment.appointment_date).label('year'),
                extract('month', Appointment.appointment_date).label('month'),
                func.count(Appointment.id).label('total'),
                func.sum(
                    case((Appointment.status == AppointmentStatus.COMPLETED, 1), else_=0)
                ).label('completed')
            )
            .filter(
                and_(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.appointment_date >= from_date,
                    Appointment.appointment_date <= to_date
                )
            )
            .group_by(
                extract('year', Appointment.appointment_date),
                extract('month', Appointment.appointment_date)
            )
            .order_by(
                extract('year', Appointment.appointment_date),
                extract('month', Appointment.appointment_date)
            )
            .all()
        )
        
        return [
            {
                'year': int(d.year),
                'month': int(d.month),
                'total_appointments': d.total,
                'completed_appointments': d.completed
            }
            for d in data
        ]
    
    def _get_monthly_patient_growth(
        self,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """Get monthly patient registration trend"""
        data = (
            self.db.query(
                extract('year', Patient.created_at).label('year'),
                extract('month', Patient.created_at).label('month'),
                func.count(Patient.id).label('new_patients')
            )
            .filter(
                and_(
                    Patient.tenant_id == self.tenant_id,
                    func.date(Patient.created_at) >= from_date,
                    func.date(Patient.created_at) <= to_date
                )
            )
            .group_by(
                extract('year', Patient.created_at),
                extract('month', Patient.created_at)
            )
            .order_by(
                extract('year', Patient.created_at),
                extract('month', Patient.created_at)
            )
            .all()
        )
        
        return [
            {
                'year': int(d.year),
                'month': int(d.month),
                'new_patients': d.new_patients
            }
            for d in data
        ]
    
    def _get_avg_consultation_time_for_doctor(
        self,
        doctor_id: int,
        from_date: date,
        to_date: date
    ) -> Optional[float]:
        """Get average consultation time for a doctor"""
        # This would require tracking visit start/end times
        # Placeholder for now
        
        return None