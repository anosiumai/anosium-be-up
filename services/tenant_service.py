from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from repositories.tenant import TenantRepository
from repositories.user import UserRepository
from schemas.tenant import TenantCreate, TenantUpdate, SubscriptionUpdate
from models.tenant import Tenant, SubscriptionTier, SubscriptionStatus
from models.user import UserRole
from services.base_service import BaseService
from core.security import get_password_hash

class TenantService(BaseService):
    """Tenant management service"""
    
    def __init__(self, db: Session, current_user_id: Optional[int] = None):
        super().__init__(db, current_user_id=current_user_id)
        self.tenant_repo = TenantRepository(db, current_user_id)
        self.user_repo = UserRepository(db)
    
    def create_tenant(self, tenant_in: TenantCreate) -> Tenant:
        """Create new tenant with admin user"""
        # Check if slug is available
        if not self.tenant_repo.check_slug_available(tenant_in.slug):
            raise ValueError(f"Slug '{tenant_in.slug}' is already taken")
        
        # Check if email exists
        if self.tenant_repo.get_by_email(tenant_in.email):
            raise ValueError(f"Email '{tenant_in.email}' is already registered")
        
        # Create tenant
        tenant_data = {
            'name': tenant_in.name,
            'slug': tenant_in.slug,
            'email': tenant_in.email,
            'phone': tenant_in.phone,
            'address': tenant_in.address,
            'city': tenant_in.city,
            'state': tenant_in.state,
            'country': tenant_in.country,
            'postal_code': tenant_in.postal_code,
            'subscription_tier': SubscriptionTier.FREE,
            'subscription_status': SubscriptionStatus.TRIAL,
            'subscription_start_date': datetime.utcnow(),
            'subscription_end_date': datetime.utcnow() + timedelta(days=14),  # 14-day trial
            'enabled_features': {
                'ai_chatbot': False,
                'advanced_billing': False,
                'analytics': False,
                'max_doctors': 2,
                'max_patients': 50
            },
            'is_active': True
        }
        
        tenant = self.tenant_repo.create(tenant_data)
        
        # Create admin user for tenant
        admin_user_data = {
            'tenant_id': tenant.id,
            'email': tenant_in.email,
            'hashed_password': get_password_hash(tenant_in.password),
            'first_name': tenant_in.admin_first_name,
            'last_name': tenant_in.admin_last_name,
            'role': UserRole.CLINIC_ADMIN,
            'is_active': True,
            'is_verified': False
        }
        
        self.user_repo.create(admin_user_data)
        
        self.commit()
        
        return tenant
    
    def get_tenant(self, tenant_id: int) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.tenant_repo.get(tenant_id)
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        return self.tenant_repo.get_by_slug(slug)
    
    def get_tenants(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get list of tenants"""
        if search:
            # Implement search logic
            tenants = self.tenant_repo.search(
                search,
                ['name', 'slug', 'email'],
                skip,
                limit
            )
        else:
            tenants = self.tenant_repo.get_multi(skip, limit, filters)
        
        total = self.tenant_repo.count(filters)
        
        return {
            'items': tenants,
            'total': total
        }
    
    def update_tenant(self, tenant_id: int, tenant_in: TenantUpdate) -> Optional[Tenant]:
        """Update tenant information"""
        tenant = self.tenant_repo.get(tenant_id)
        if not tenant:
            return None
        
        update_data = tenant_in.dict(exclude_unset=True)
        
        # Check slug availability if being updated
        if 'slug' in update_data and update_data['slug'] != tenant.slug:
            if not self.tenant_repo.check_slug_available(update_data['slug'], tenant_id):
                raise ValueError(f"Slug '{update_data['slug']}' is already taken")
        
        tenant = self.tenant_repo.update(tenant_id, update_data)
        self.commit()
        
        return tenant
    
    def update_subscription(
        self,
        tenant_id: int,
        subscription_in: SubscriptionUpdate
    ) -> Optional[Tenant]:
        """Update tenant subscription"""
        tenant = self.tenant_repo.get(tenant_id)
        if not tenant:
            return None
        
        update_data = subscription_in.dict(exclude_unset=True)
        
        # Set subscription dates if changing tier
        if 'subscription_tier' in update_data:
            if 'subscription_start_date' not in update_data:
                update_data['subscription_start_date'] = datetime.utcnow()
            
            # Set default features based on tier
            tier = update_data['subscription_tier']
            update_data['enabled_features'] = self._get_tier_features(tier)
        
        tenant = self.tenant_repo.update(tenant_id, update_data)
        self.commit()
        
        return tenant
    
    def activate_tenant(self, tenant_id: int) -> bool:
        """Activate tenant"""
        tenant = self.tenant_repo.update(tenant_id, {'is_active': True})
        if tenant:
            self.commit()
            return True
        return False
    
    def deactivate_tenant(self, tenant_id: int, reason: Optional[str] = None) -> bool:
        """Deactivate tenant"""
        update_data = {
            'is_active': False,
            'settings': {'deactivation_reason': reason} if reason else {}
        }
        
        tenant = self.tenant_repo.update(tenant_id, update_data)
        if tenant:
            self.commit()
            return True
        return False
    
    def delete_tenant(self, tenant_id: int) -> bool:
        """Delete tenant (hard delete)"""
        success = self.tenant_repo.delete(tenant_id, soft=False)
        if success:
            self.commit()
        return success
    
    def get_tenant_with_stats(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Get tenant with usage statistics"""
        tenant = self.tenant_repo.get(tenant_id)
        if not tenant:
            return None
        
        stats = self.tenant_repo.get_tenant_usage_stats(tenant_id)
        
        return {
            **tenant.__dict__,
            **stats
        }
    
    def get_tenant_usage(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Get tenant resource usage"""
        tenant = self.tenant_repo.get(tenant_id)
        if not tenant:
            return None
        
        usage = self.tenant_repo.get_tenant_usage_stats(tenant_id)
        limits = tenant.enabled_features
        
        return {
            'usage': usage,
            'limits': limits,
            'subscription_tier': tenant.subscription_tier.value,
            'subscription_status': tenant.subscription_status.value
        }
    
    def check_feature_access(self, tenant_id: int, feature: str) -> bool:
        """Check if tenant has access to a feature"""
        tenant = self.tenant_repo.get(tenant_id)
        if not tenant:
            return False
        
        return tenant.enabled_features.get(feature, False)
    
    def _get_tier_features(self, tier: SubscriptionTier) -> Dict[str, Any]:
        """Get default features for subscription tier"""
        features = {
            SubscriptionTier.FREE: {
                'ai_chatbot': False,
                'advanced_billing': False,
                'analytics': False,
                'max_doctors': 2,
                'max_patients': 50,
                'max_appointments_per_month': 100
            },
            SubscriptionTier.BASIC: {
                'ai_chatbot': True,
                'advanced_billing': True,
                'analytics': False,
                'max_doctors': 5,
                'max_patients': 500,
                'max_appointments_per_month': 1000
            },
            SubscriptionTier.PREMIUM: {
                'ai_chatbot': True,
                'advanced_billing': True,
                'analytics': True,
                'max_doctors': 20,
                'max_patients': 5000,
                'max_appointments_per_month': 10000
            },
            SubscriptionTier.ENTERPRISE: {
                'ai_chatbot': True,
                'advanced_billing': True,
                'analytics': True,
                'max_doctors': -1,  # Unlimited
                'max_patients': -1,
                'max_appointments_per_month': -1
            }
        }
        
        return features.get(tier, features[SubscriptionTier.FREE])