from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class DailyMetrics(Base):
    """
    Aggregated daily metrics for performance monitoring
    """
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    
    # Appointments
    total_appointments = Column(Integer, default=0)
    completed_appointments = Column(Integer, default=0)
    cancelled_appointments = Column(Integer, default=0)
    no_show_appointments = Column(Integer, default=0)
    
    # Patients
    new_patients = Column(Integer, default=0)
    returning_patients = Column(Integer, default=0)
    
    # Revenue
    total_revenue = Column(Integer, default=0)  # In cents
    paid_revenue = Column(Integer, default=0)
    pending_revenue = Column(Integer, default=0)
    
    # AI Metrics
    ai_leads_captured = Column(Integer, default=0)
    ai_leads_converted = Column(Integer, default=0)
    ai_bookings = Column(Integer, default=0)
    
    # Performance
    average_wait_time_minutes = Column(Float)
    average_consultation_time_minutes = Column(Float)
    
    # Additional Metrics
    metrics_json = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemHealthMetric(Base):
    """
    System health monitoring for reliability
    """
    __tablename__ = "system_health_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Timestamp
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Database
    db_connection_count = Column(Integer)
    db_query_avg_time_ms = Column(Float)
    db_slow_query_count = Column(Integer)
    
    # API
    api_request_count = Column(Integer)
    api_avg_response_time_ms = Column(Float)
    api_error_count = Column(Integer)
    api_error_rate = Column(Float)
    
    # AI Services
    ai_chatbot_response_time_ms = Column(Float)
    ai_chatbot_success_rate = Column(Float)
    
    # Resource Usage
    cpu_usage_percent = Column(Float)
    memory_usage_percent = Column(Float)
    disk_usage_percent = Column(Float)
    
    # External Services
    external_services_status = Column(JSON)  # Status of SMS, email, payment gateways