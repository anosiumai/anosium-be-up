from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models.tenant import Tenant, SubscriptionTier, SubscriptionStatus
from repositories.base import BaseRepository

class TenantRepository(BaseRepository[Tenant]):
    """Repository for Tenant operations"""
    
    def __init__(self, db: Session, current_user_id: Optional[int] = None):
        super().__init__(db, Tenant, tenant_id=None, current_user_id=current_user_id)
    
    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        return self.db.query(Tenant).filter(Tenant.slug == slug).first()
    
    def get_by_email(self, email: str) -> Optional[Tenant]:
        """Get tenant by email"""
        return self.db.query(Tenant).filter(Tenant.email == email).first()
    
    def check_slug_available(self, slug: str, exclude_id: Optional[int] = None) -> bool:
        """Check if slug is available"""
        query = self.db.query(Tenant).filter(Tenant.slug == slug)
        
        if exclude_id:
            query = query.filter(Tenant.id != exclude_id)
        
        return query.first() is None
    
    def get_active_tenants(self, skip: int = 0, limit: int = 100) -> List[Tenant]:
        """Get all active tenants"""
        return (
            self.db.query(Tenant)
            .filter(Tenant.is_active == True)
            .order_by(Tenant.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_subscription_tier(
        self, 
        tier: SubscriptionTier,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tenant]:
        """Get tenants by subscription tier"""
        return (
            self.db.query(Tenant)
            .filter(Tenant.subscription_tier == tier)
            .order_by(Tenant.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_expiring_subscriptions(self, days: int = 7) -> List[Tenant]:
        """Get tenants with subscriptions expiring in N days"""
        from datetime import datetime, timedelta
        
        expiry_date = datetime.utcnow() + timedelta(days=days)
        
        return (
            self.db.query(Tenant)
            .filter(
                and_(
                    Tenant.subscription_end_date <= expiry_date,
                    Tenant.subscription_end_date >= datetime.utcnow(),
                    Tenant.is_active == True
                )
            )
            .all()
        )
    
    def count_by_tier(self) -> Dict[str, int]:
        """Count tenants by subscription tier"""
        results = (
            self.db.query(
                Tenant.subscription_tier,
                func.count(Tenant.id).label('count')
            )
            .filter(Tenant.is_active == True)
            .group_by(Tenant.subscription_tier)
            .all()
        )
        
        return {tier.value: count for tier, count in results}
    
    def get_tenant_usage_stats(self, tenant_id: int) -> Dict[str, Any]:
        """Get resource usage for a tenant"""
        from models.patient import Patient
        from models.doctor import Doctor
        from models.user import User
        from models.appointment import Appointment
        
        stats = {
            'total_patients': self.db.query(func.count(Patient.id)).filter(Patient.tenant_id == tenant_id).scalar(),
            'active_patients': self.db.query(func.count(Patient.id)).filter(
                and_(Patient.tenant_id == tenant_id, Patient.is_active == True)
            ).scalar(),
            'total_doctors': self.db.query(func.count(Doctor.id)).filter(Doctor.tenant_id == tenant_id).scalar(),
            'active_doctors': self.db.query(func.count(Doctor.id)).filter(
                and_(Doctor.tenant_id == tenant_id, Doctor.is_active == True)
            ).scalar(),
            'total_users': self.db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar(),
            'active_users': self.db.query(func.count(User.id)).filter(
                and_(User.tenant_id == tenant_id, User.is_active == True)
            ).scalar(),
            'total_appointments': self.db.query(func.count(Appointment.id)).filter(
                Appointment.tenant_id == tenant_id
            ).scalar(),
        }
        
        return stats