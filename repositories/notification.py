from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timedelta

from models.notification import (
    Notification, NotificationTemplate, NotificationPreference,
    NotificationType, NotificationChannel, NotificationStatus
)
from repositories.base import BaseRepository

class NotificationRepository(BaseRepository[Notification]):
    """Repository for Notification operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(Notification, db, tenant_id, current_user_id)
    
    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        unread_only: bool = False
    ) -> List[Notification]:
        """Get notifications for a user"""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        query = self._apply_tenant_filter(query)
        
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        
        return (
            query.order_by(desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_patient(
        self,
        patient_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Notification]:
        """Get notifications for a patient"""
        query = self.db.query(Notification).filter(Notification.patient_id == patient_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_pending_notifications(self, limit: int = 100) -> List[Notification]:
        """Get pending notifications to be sent"""
        now = datetime.utcnow()
        
        query = self.db.query(Notification).filter(
            and_(
                Notification.status == NotificationStatus.PENDING,
                or_(
                    Notification.scheduled_for.is_(None),
                    Notification.scheduled_for <= now
                )
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(Notification.scheduled_for).limit(limit).all()
    
    def get_failed_notifications(
        self,
        retry_eligible_only: bool = True,
        limit: int = 100
    ) -> List[Notification]:
        """Get failed notifications"""
        query = self.db.query(Notification).filter(
            Notification.status == NotificationStatus.FAILED
        )
        query = self._apply_tenant_filter(query)
        
        if retry_eligible_only:
            query = query.filter(
                Notification.retry_count < Notification.max_retries
            )
        
        return query.limit(limit).all()
    
    def mark_as_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        notification = self.get(notification_id)
        if not notification:
            return False
        
        notification.read_at = datetime.utcnow()
        notification.status = NotificationStatus.READ
        self.db.flush()
        
        return True
    
    def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        query = self.db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.read_at.is_(None)
            )
        )
        query = self._apply_tenant_filter(query)
        
        count = query.update({
            'read_at': datetime.utcnow(),
            'status': NotificationStatus.READ
        })
        
        self.db.flush()
        return count
    
    def count_unread(self, user_id: int) -> int:
        """Count unread notifications for a user"""
        query = self.db.query(func.count(Notification.id)).filter(
            and_(
                Notification.user_id == user_id,
                Notification.read_at.is_(None)
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.scalar()
    
    def get_statistics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get notification statistics"""
        query = self.db.query(Notification)
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(Notification.created_at >= from_date)
        
        if to_date:
            query = query.filter(Notification.created_at <= to_date)
        
        total = query.count()
        sent = query.filter(Notification.status == NotificationStatus.SENT).count()
        delivered = query.filter(Notification.status == NotificationStatus.DELIVERED).count()
        failed = query.filter(Notification.status == NotificationStatus.FAILED).count()
        
        return {
            'total': total,
            'sent': sent,
            'delivered': delivered,
            'failed': failed,
            'delivery_rate': (delivered / total * 100) if total > 0 else 0
        }

class NotificationTemplateRepository(BaseRepository[NotificationTemplate]):
    """Repository for Notification Template operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(NotificationTemplate, db, tenant_id, current_user_id)
    
    def get_by_code(self, code: str) -> Optional[NotificationTemplate]:
        """Get template by code"""
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.code == code
        )
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_type_and_channel(
        self,
        notification_type: NotificationType,
        channel: NotificationChannel
    ) -> List[NotificationTemplate]:
        """Get templates by type and channel"""
        query = self.db.query(NotificationTemplate).filter(
            and_(
                NotificationTemplate.type == notification_type,
                NotificationTemplate.channel == channel,
                NotificationTemplate.is_active == True
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.all()
    
    def get_active_templates(self) -> List[NotificationTemplate]:
        """Get all active templates"""
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.is_active == True
        )
        query = self._apply_tenant_filter(query)
        
        return query.all()

class NotificationPreferenceRepository(BaseRepository[NotificationPreference]):
    """Repository for Notification Preference operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(NotificationPreference, db, tenant_id, current_user_id)
    
    def get_by_user(self, user_id: int) -> Optional[NotificationPreference]:
        """Get preferences for a user"""
        return (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .first()
        )
    
    def get_by_patient(self, patient_id: int) -> Optional[NotificationPreference]:
        """Get preferences for a patient"""
        return (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.patient_id == patient_id)
            .first()
        )