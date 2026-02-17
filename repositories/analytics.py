from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta

from models.analytics import DailyMetrics, SystemHealthMetric
from repositories.base import BaseRepository

class DailyMetricsRepository(BaseRepository[DailyMetrics]):
    """Repository for Daily Metrics operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(db, DailyMetrics, tenant_id, current_user_id)
    
    def get_by_date(self, metric_date: date) -> Optional[DailyMetrics]:
        """Get metrics for a specific date"""
        query = self.db.query(DailyMetrics).filter(
            DailyMetrics.metric_date == metric_date
        )
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_date_range(
        self,
        from_date: date,
        to_date: date
    ) -> List[DailyMetrics]:
        """Get metrics for a date range"""
        query = self.db.query(DailyMetrics).filter(
            and_(
                DailyMetrics.metric_date >= from_date,
                DailyMetrics.metric_date <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(DailyMetrics.metric_date).all()
    
    def get_last_n_days(self, days: int = 30) -> List[DailyMetrics]:
        """Get metrics for last N days"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        return self.get_date_range(start_date, end_date)
    
    def aggregate_metrics(
        self,
        from_date: date,
        to_date: date
    ) -> Dict[str, Any]:
        """Aggregate metrics for a period"""
        query = self.db.query(
            func.sum(DailyMetrics.total_appointments).label('total_appointments'),
            func.sum(DailyMetrics.completed_appointments).label('completed_appointments'),
            func.sum(DailyMetrics.cancelled_appointments).label('cancelled_appointments'),
            func.sum(DailyMetrics.new_patients).label('new_patients'),
            func.sum(DailyMetrics.total_revenue).label('total_revenue'),
            func.sum(DailyMetrics.paid_revenue).label('paid_revenue'),
            func.avg(DailyMetrics.average_wait_time_minutes).label('avg_wait_time'),
            func.avg(DailyMetrics.average_consultation_time_minutes).label('avg_consultation_time')
        ).filter(
            and_(
                DailyMetrics.metric_date >= from_date,
                DailyMetrics.metric_date <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        result = query.first()
        
        return {
            'total_appointments': result.total_appointments or 0,
            'completed_appointments': result.completed_appointments or 0,
            'cancelled_appointments': result.cancelled_appointments or 0,
            'new_patients': result.new_patients or 0,
            'total_revenue': result.total_revenue or 0,
            'paid_revenue': result.paid_revenue or 0,
            'avg_wait_time': float(result.avg_wait_time or 0),
            'avg_consultation_time': float(result.avg_consultation_time or 0)
        }

class SystemHealthMetricRepository(BaseRepository[SystemHealthMetric]):
    """Repository for System Health Metric operations"""
    
    def __init__(self, db: Session):
        super().__init__(db, SystemHealthMetric, tenant_id=None, current_user_id=None)
    
    def get_latest(self) -> Optional[SystemHealthMetric]:
        """Get latest health metric"""
        return (
            self.db.query(SystemHealthMetric)
            .order_by(SystemHealthMetric.recorded_at.desc())
            .first()
        )
    
    def get_recent(self, limit: int = 100) -> List[SystemHealthMetric]:
        """Get recent health metrics"""
        return (
            self.db.query(SystemHealthMetric)
            .order_by(SystemHealthMetric.recorded_at.desc())
            .limit(limit)
            .all()
        )
    
    def get_date_range(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> List[SystemHealthMetric]:
        """Get health metrics in date range"""
        return (
            self.db.query(SystemHealthMetric)
            .filter(
                and_(
                    SystemHealthMetric.recorded_at >= from_date,
                    SystemHealthMetric.recorded_at <= to_date
                )
            )
            .order_by(SystemHealthMetric.recorded_at)
            .all()
        )