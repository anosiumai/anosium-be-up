from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc
from datetime import datetime, timedelta

# Import SQLAlchemy models, not Pydantic schemas
from models.audit import AuditLog, AuditAction, DataAccessLog
from repositories.base import BaseRepository

class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for Audit Log operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(AuditLog, db, tenant_id, current_user_id)
    
    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs for a user"""
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_resource(
        self,
        resource_type: str,
        resource_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs for a specific resource"""
        query = self.db.query(AuditLog).filter(
            and_(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id
            )
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_action(
        self,
        action: AuditAction,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs by action type"""
        query = self.db.query(AuditLog).filter(AuditLog.action == action)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_date_range(
        self,
        from_date: datetime,
        to_date: datetime,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs in date range"""
        query = self.db.query(AuditLog).filter(
            and_(
                AuditLog.created_at >= from_date,
                AuditLog.created_at <= to_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def search_audit_logs(
        self,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[AuditAction] = None, # pyright: ignore[reportInvalidTypeForm]
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Advanced search for audit logs"""
        query = self.db.query(AuditLog)
        query = self._apply_tenant_filter(query)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if from_date:
            query = query.filter(AuditLog.created_at >= from_date)
        
        if to_date:
            query = query.filter(AuditLog.created_at <= to_date)
        
        return (
            query.order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def count_by_action(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Count audit logs by action"""
        query = self.db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(AuditLog.created_at >= from_date)
        
        if to_date:
            query = query.filter(AuditLog.created_at <= to_date)
        
        results = query.group_by(AuditLog.action).all()
        
        return {action.value: count for action, count in results}

class DataAccessLogRepository(BaseRepository[DataAccessLog]):
    """Repository for Data Access Log operations (HIPAA compliance)"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(DataAccessLog, db, tenant_id, current_user_id)
    
    def get_by_patient(
        self,
        patient_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[DataAccessLog]:
        """Get access logs for a patient"""
        query = self.db.query(DataAccessLog).filter(
            DataAccessLog.patient_id == patient_id
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(DataAccessLog.accessed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[DataAccessLog]:
        """Get access logs by user"""
        query = self.db.query(DataAccessLog).filter(
            DataAccessLog.user_id == user_id
        )
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(DataAccessLog.accessed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def log_patient_access(
        self,
        patient_id: int,
        user_id: int,
        access_type: str,
        accessed_fields: Optional[List[str]] = None,
        purpose: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> DataAccessLog:
        """Log patient data access"""
        access_log = DataAccessLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            patient_id=patient_id,
            access_type=access_type,
            accessed_fields=accessed_fields or [],
            purpose=purpose,
            ip_address=ip_address,
            accessed_at=datetime.utcnow()
        )
        
        self.db.add(access_log)
        self.db.flush()
        
        return access_log