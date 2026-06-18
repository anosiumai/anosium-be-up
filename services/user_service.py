"""
User Service
Handles all user-related operations including authentication, role management, 
permissions, and activity tracking
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from core.security import get_password_hash, verify_password
from core.email import dispatch_email

from models.user import User, UserRole
from models.tenant import Tenant
from repositories.user import UserRepository
from schemas.user import (
    UserCreate, UserUpdate, User as UserSchema,
    PasswordChange
)


class UserService:
    """Service for user operations"""
    
    def __init__(self, db: Session, tenant_id: Optional[int], current_user_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id
        self.user_repo = UserRepository(db, tenant_id, current_user_id)
    
    # ============================================================================
    # CRUD OPERATIONS
    # ============================================================================
    
    def create_user(self, user_in: UserCreate) -> UserSchema:
        """
        Create a new user account.

        Side-effects
        ------------
        A welcome email is dispatched on success via `dispatch_email` (best-
        effort — a delivery failure does not roll back user creation).  When
        `user_in.tenant_id` is set, the tenant name is resolved and included
        in the email so the staff member knows which clinic they're joining.
        """
        # Check if email already exists
        if self.user_repo.check_email_exists(user_in.email):
            raise ValueError(f"Email '{user_in.email}' already exists")
        
        # Validate tenant if not super admin
        if user_in.role != UserRole.SUPER_ADMIN:
            if not user_in.tenant_id:
                raise ValueError("tenant_id is required for non-super-admin users")
            
            tenant = self.db.query(Tenant).filter(Tenant.id == user_in.tenant_id).first()
            if not tenant:
                raise ValueError("Tenant not found")
        
        hashed_password = get_password_hash(user_in.password)
        
        user = User(
            email=user_in.email.lower(),
            hashed_password=hashed_password,
            role=user_in.role,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            phone=user_in.phone,
            tenant_id=user_in.tenant_id,
            permissions={},
            is_active=True,
            is_verified=False
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # --- welcome email (best-effort) -----------------------------------
        tenant_name: Optional[str] = None
        if user_in.tenant_id:
            t = self.db.query(Tenant).filter(Tenant.id == user_in.tenant_id).first()
            tenant_name = t.name if t else None

        dispatch_email(
            "welcome",
            to_email=user.email,
            user_name=user.full_name,
            tenant_name=tenant_name,
            role=user.role.value if user.role else None,
        )

        return UserSchema.from_orm(user)
    
    def get_user(self, user_id: int) -> Optional[UserSchema]:
        """Get user by ID"""
        user = self.user_repo.get(user_id)
        if user:
            return UserSchema.from_orm(user)
        return None
    
    def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get list of users with filtering and search"""
        query = self.db.query(User)
        
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
            
        if filters is None or 'is_active' not in filters:
            query = query.filter(User.is_active == True)
        
        if search:
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        if filters:
            if 'role' in filters:
                query = query.filter(User.role == filters['role'])
            if 'is_active' in filters:
                query = query.filter(User.is_active == filters['is_active'])
            if 'is_verified' in filters:
                query = query.filter(User.is_verified == filters['is_verified'])
        
        total = query.count()
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            'items': [UserSchema.from_orm(user) for user in users],
            'total': total
        }
    
    def update_user(self, user_id: int, user_in: UserUpdate) -> Optional[UserSchema]:
        """Update user"""
        user = self.user_repo.get(user_id)
        if not user:
            return None
        
        update_data = user_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return UserSchema.from_orm(user)
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete)"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        user.is_active = False
        self.db.commit()
        return True
    
    # ============================================================================
    # AUTHENTICATION AND AUTHORIZATION
    # ============================================================================
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.user_repo.get_by_email(email.lower())
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        self.user_repo.update_last_login(user.id)
        self.db.commit()
        return user
    
    def change_password(self, user_id: int, password_change: PasswordChange) -> bool:
        """Change user password"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        if not verify_password(password_change.old_password, user.hashed_password):
            return False
        user.hashed_password = get_password_hash(password_change.new_password)
        self.db.commit()
        return True
    
    def get_user_by_email(self, email: str) -> Optional[UserSchema]:
        """Get user by email"""
        user = self.user_repo.get_by_email(email.lower())
        if user:
            return UserSchema.from_orm(user)
        return None
    
    def verify_user(self, user_id: int) -> bool:
        """Mark user as verified"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        user.is_verified = True
        self.db.commit()
        return True
    
    def admin_reset_password(self, user_id: int, new_password: str) -> bool:
        """Reset user password (admin function)"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        return True
    
    # ============================================================================
    # ROLE AND PERMISSIONS MANAGEMENT
    # ============================================================================
    
    def change_user_role(self, user_id: int, new_role: UserRole) -> Optional[UserSchema]:
        """Change user's role"""
        user = self.user_repo.get(user_id)
        if not user:
            return None
        
        if new_role == UserRole.DOCTOR and user.role != UserRole.DOCTOR:
            pass  # Doctor profile created separately
        elif user.role == UserRole.DOCTOR and new_role != UserRole.DOCTOR:
            if user.doctor_profile:
                raise ValueError(
                    "Cannot change role from DOCTOR when doctor profile exists. "
                    "Deactivate doctor profile first."
                )
        
        user.role = new_role
        self.db.commit()
        self.db.refresh(user)
        return UserSchema.from_orm(user)
    
    def update_user_permissions(self, user_id: int, permissions: Dict[str, Any]) -> Optional[UserSchema]:
        """Update user's granular permissions"""
        user = self.user_repo.get(user_id)
        if not user:
            return None
        current_permissions = user.permissions or {}
        current_permissions.update(permissions)
        user.permissions = current_permissions
        self.db.commit()
        self.db.refresh(user)
        return UserSchema.from_orm(user)
    
    def check_permission(self, user_id: int, permission: str) -> bool:
        """Check if user has a specific permission"""
        user = self.user_repo.get(user_id)
        if not user or not user.is_active:
            return False
        if user.role == UserRole.SUPER_ADMIN:
            return True
        if user.role == UserRole.CLINIC_ADMIN:
            restricted = ['manage_tenants', 'manage_super_admins']
            return permission not in restricted
        permissions = user.permissions or {}
        return permissions.get(permission, False)
    
    # ============================================================================
    # USER MANAGEMENT
    # ============================================================================
    
    def activate_user(self, user_id: int) -> bool:
        """Activate user account"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        user.is_active = True
        self.db.commit()
        return True
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate user account"""
        user = self.user_repo.get(user_id)
        if not user:
            return False
        user.is_active = False
        self.db.commit()
        return True
    
    def get_users_by_role(self, role: UserRole, skip: int = 0, limit: int = 100) -> List[UserSchema]:
        """Get users by role"""
        users = self.user_repo.get_by_role(role, skip, limit)
        return [UserSchema.from_orm(user) for user in users]
    
    def search_users(self, search_term: str, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Search users by name or email"""
        users = self.user_repo.search_users(search_term, skip, limit)
        
        query = self.db.query(User).filter(
            or_(
                User.first_name.ilike(f"%{search_term}%"),
                User.last_name.ilike(f"%{search_term}%"),
                User.email.ilike(f"%{search_term}%")
            )
        )
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
        
        return {
            'items': [UserSchema.from_orm(user) for user in users],
            'total': query.count()
        }
    
    # ============================================================================
    # STATISTICS AND REPORTING
    # ============================================================================
    
    def get_users_summary(self) -> Dict[str, Any]:
        """Get user statistics summary"""
        query = self.db.query(User)
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
        
        total_users = query.count()
        active_users = query.filter(User.is_active == True).count()
        users_by_role = self.user_repo.count_by_role()
        recent_users = self.user_repo.get_recently_registered(days=7, limit=10)
        verified_count = query.filter(User.is_verified == True).count()
        unverified_count = query.filter(User.is_verified == False).count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'verified_users': verified_count,
            'unverified_users': unverified_count,
            'users_by_role': users_by_role,
            'recent_registrations': [
                {
                    'id': u.id,
                    'name': u.full_name,
                    'email': u.email,
                    'role': u.role.value,
                    'created_at': u.created_at.isoformat()
                }
                for u in recent_users
            ]
        }
    
    def get_user_activity(self, user_id: int, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get user activity statistics"""
        user = self.user_repo.get(user_id)
        if not user:
            return None
        
        return {
            'user_id': user_id,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'account_created': user.created_at.isoformat(),
            'is_active': user.is_active,
            'total_logins': None,   # Requires login-history table
            'recent_actions': [],   # Requires audit log query
            'period_days': days
        }
    
    def get_inactive_users(self, days: int = 30) -> List[UserSchema]:
        """Get users who haven't logged in for N days"""
        users = self.user_repo.get_inactive_users(days)
        return [UserSchema.from_orm(user) for user in users]
    
    # ============================================================================
    # NOTIFICATIONS AND COMMUNICATION
    # ============================================================================

    def send_welcome_email(self, user_id: int) -> bool:
        """
        (Re-)send a welcome email to a user.

        Used by the admin endpoint ``POST /users/{user_id}/send-welcome-email``
        to resend the email when the original was missed or landed in spam.

        The tenant name is resolved from the user's `tenant_id` so the email
        body can say "You've been added to <Clinic Name>".

        Returns True if the dispatch was accepted (Celery enqueue) or sent
        inline; False if the user doesn't exist.
        """
        user = self.user_repo.get(user_id)
        if not user:
            return False

        tenant_name: Optional[str] = None
        if user.tenant_id:
            t = self.db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_name = t.name if t else None

        dispatch_email(
            "welcome",
            to_email=user.email,
            user_name=user.full_name,
            tenant_name=tenant_name,
            role=user.role.value if user.role else None,
        )
        return True
    
    def send_password_reset_email(self, email: str) -> bool:
        """
        Trigger a password reset flow from the user-service side.

        This is distinct from `AuthService.create_password_reset_token`, which
        is the canonical path triggered by ``POST /auth/password/reset-request``.
        This method exists so admin tooling (or future self-service flows built
        on UserService rather than AuthService) can kick off the same flow
        without importing AuthService directly.

        Internally it delegates to AuthService to avoid duplicating token
        creation logic.

        Returns True if the user exists (email was dispatched); False otherwise.
        """
        user = self.user_repo.get_by_email(email.lower())
        if not user:
            return False

        # Import here to avoid a circular dependency at module load time
        # (AuthService → UserService path doesn't exist, but some linting
        # tools flag cross-service imports at the top level).
        from services.auth_service import AuthService

        auth_svc = AuthService(self.db)
        auth_svc.create_password_reset_token(email)
        return True

    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _validate_user_access(self, user_id: int) -> bool:
        """Validate that user belongs to current tenant"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        if user.role == UserRole.SUPER_ADMIN:
            return True
        return user.tenant_id == self.tenant_id