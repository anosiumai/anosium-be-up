"""
User Service
Handles all user-related operations including authentication, role management, 
permissions, and activity tracking
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from passlib.context import CryptContext
from core.security import get_password_hash, verify_password

from models.user import User, UserRole
from models.tenant import Tenant
from repositories.user import UserRepository
from schemas.user import (
    UserCreate, UserUpdate, User as UserSchema,
    PasswordChange
)


# Password hashing
# At the top of services/user.py
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Explicitly set rounds
    bcrypt__ident="2b"   # Use bcrypt 2b variant
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
        """Create new user"""
        # Check if email already exists
        if self.user_repo.check_email_exists(user_in.email):
            raise ValueError(f"Email '{user_in.email}' already exists")
        
        # Validate tenant if not super admin
        if user_in.role != UserRole.SUPER_ADMIN:
            if not user_in.tenant_id:
                raise ValueError("tenant_id is required for non-super-admin users")
            
            # Verify tenant exists
            tenant = self.db.query(Tenant).filter(Tenant.id == user_in.tenant_id).first()
            if not tenant:
                raise ValueError("Tenant not found")
        
        # Hash password - USE get_password_hash from core/security.py
        hashed_password = get_password_hash(user_in.password)
        
        # Create user
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
        
        return UserSchema.from_orm(user)
    
    def get_user(self, user_id: int) -> Optional[UserSchema]:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User or None if not found
        """
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
        """
        Get list of users with filtering and search
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search term for name/email
            filters: Filter criteria
            
        Returns:
            Dictionary with items and total count
        """
        query = self.db.query(User)
        
        # Apply tenant filter (unless super admin viewing all)
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
            
        if filters is None or 'is_active' not in filters:
            query = query.filter(User.is_active == True)
        
        # Apply search
        if search:
            query = query.filter(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # Apply filters
        if filters:
            if 'role' in filters:
                query = query.filter(User.role == filters['role'])
            
            if 'is_active' in filters:
                query = query.filter(User.is_active == filters['is_active'])
            
            if 'is_verified' in filters:
                query = query.filter(User.is_verified == filters['is_verified'])
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            'items': [UserSchema.from_orm(user) for user in users],
            'total': total
        }
    
    def update_user(
        self,
        user_id: int,
        user_in: UserUpdate
    ) -> Optional[UserSchema]:
        """
        Update user
        
        Args:
            user_id: User ID
            user_in: Update data
            
        Returns:
            Updated user or None if not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return None
        
        # Update fields
        update_data = user_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        
        return UserSchema.from_orm(user)
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete user (soft delete)
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted successfully, False if not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return False
        
        # Soft delete - deactivate
        user.is_active = False
        
        self.db.commit()
        
        return True
    
    # ============================================================================
    # AUTHENTICATION AND AUTHORIZATION
    # ============================================================================
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.user_repo.get_by_email(email.lower())
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        # USE verify_password from core/security.py
        if not verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        self.user_repo.update_last_login(user.id)
        self.db.commit()
        
        return user
    
    def change_password(
        self,
        user_id: int,
        password_change: PasswordChange
    ) -> bool:
        """
        Change user password
        
        Args:
            user_id: User ID
            password_change: Password change data
            
        Returns:
            True if changed successfully, False if not found or wrong password
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return False
        
        # Verify old password - USE verify_password from core/security.py
        if not verify_password(password_change.old_password, user.hashed_password):
            return False
        
        # Set new password - USE get_password_hash from core/security.py
        user.hashed_password = get_password_hash(password_change.new_password)
        
        self.db.commit()
        
        return True
    
    def get_user_by_email(self, email: str) -> Optional[UserSchema]:
        """
        Get user by email
        
        Args:
            email: User email
            
        Returns:
            User or None if not found
        """
        user = self.user_repo.get_by_email(email.lower())
        
        if user:
            return UserSchema.from_orm(user)
        
        return None
    
    def verify_user(self, user_id: int) -> bool:
        """
        Mark user as verified
        
        Args:
            user_id: User ID
            
        Returns:
            True if verified successfully, False if not found
        """
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
        """
        Change user's role
        
        Args:
            user_id: User ID
            new_role: New role to assign
            
        Returns:
            Updated user or None if not found
            
        Raises:
            ValueError: If role change is invalid
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return None
        
        # Validate role change
        # If changing to/from DOCTOR role, check doctor profile
        if new_role == UserRole.DOCTOR and user.role != UserRole.DOCTOR:
            # Changing to doctor - should have doctor profile created separately
            pass
        elif user.role == UserRole.DOCTOR and new_role != UserRole.DOCTOR:
            # Changing from doctor - check if has doctor profile
            if user.doctor_profile:
                raise ValueError(
                    "Cannot change role from DOCTOR when doctor profile exists. "
                    "Deactivate doctor profile first."
                )
        
        user.role = new_role
        
        self.db.commit()
        self.db.refresh(user)
        
        return UserSchema.from_orm(user)
    
    def update_user_permissions(
        self,
        user_id: int,
        permissions: Dict[str, Any]
    ) -> Optional[UserSchema]:
        """
        Update user's granular permissions
        
        Args:
            user_id: User ID
            permissions: Permissions dictionary
            
        Returns:
            Updated user or None if not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return None
        
        # Merge with existing permissions
        current_permissions = user.permissions or {}
        current_permissions.update(permissions)
        
        user.permissions = current_permissions
        
        self.db.commit()
        self.db.refresh(user)
        
        return UserSchema.from_orm(user)
    
    def check_permission(
        self,
        user_id: int,
        permission: str
    ) -> bool:
        """
        Check if user has a specific permission
        
        Args:
            user_id: User ID
            permission: Permission to check
            
        Returns:
            True if user has permission, False otherwise
        """
        user = self.user_repo.get(user_id)
        
        if not user or not user.is_active:
            return False
        
        # Super admins have all permissions
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Clinic admins have most permissions
        if user.role == UserRole.CLINIC_ADMIN:
            # Define restricted permissions for clinic admins
            restricted = ['manage_tenants', 'manage_super_admins']
            return permission not in restricted
        
        # Check granular permissions
        permissions = user.permissions or {}
        return permissions.get(permission, False)
    
    # ============================================================================
    # USER MANAGEMENT
    # ============================================================================
    
    def activate_user(self, user_id: int) -> bool:
        """
        Activate user account
        
        Args:
            user_id: User ID
            
        Returns:
            True if activated successfully, False if not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return False
        
        user.is_active = True
        
        self.db.commit()
        
        return True
    
    def deactivate_user(self, user_id: int) -> bool:
        """
        Deactivate user account
        
        Args:
            user_id: User ID
            
        Returns:
            True if deactivated successfully, False if not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return False
        
        user.is_active = False
        
        self.db.commit()
        
        return True
    
    def get_users_by_role(
        self,
        role: UserRole,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserSchema]:
        """
        Get users by role
        
        Args:
            role: User role
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of users
        """
        users = self.user_repo.get_by_role(role, skip, limit)
        
        return [UserSchema.from_orm(user) for user in users]
    
    def search_users(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Search users by name or email
        
        Args:
            search_term: Search query
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with items and total count
        """
        users = self.user_repo.search_users(search_term, skip, limit)
        
        # Get total count
        query = self.db.query(User).filter(
            or_(
                User.first_name.ilike(f"%{search_term}%"),
                User.last_name.ilike(f"%{search_term}%"),
                User.email.ilike(f"%{search_term}%")
            )
        )
        
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
        
        total = query.count()
        
        return {
            'items': [UserSchema.from_orm(user) for user in users],
            'total': total
        }
    
    # ============================================================================
    # STATISTICS AND REPORTING
    # ============================================================================
    
    def get_users_summary(self) -> Dict[str, Any]:
        """
        Get user statistics summary
        
        Returns:
            Statistics dictionary
        """
        query = self.db.query(User)
        
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
        
        # Total users
        total_users = query.count()
        
        # Active users
        active_users = query.filter(User.is_active == True).count()
        
        # Users by role
        users_by_role = self.user_repo.count_by_role()
        
        # Recently registered (last 7 days)
        recent_users = self.user_repo.get_recently_registered(days=7, limit=10)
        
        # Verified vs unverified
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
    
    def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Get user activity statistics
        
        Args:
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            Activity statistics or None if user not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return None
        
        # This is a placeholder - actual implementation would track
        # login history, actions performed, etc. in a separate audit log table
        
        return {
            'user_id': user_id,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'account_created': user.created_at.isoformat(),
            'is_active': user.is_active,
            'total_logins': None,  # Would come from login history table
            'recent_actions': [],  # Would come from audit log table
            'period_days': days
        }
    
    def get_inactive_users(self, days: int = 30) -> List[UserSchema]:
        """
        Get users who haven't logged in for N days
        
        Args:
            days: Number of days of inactivity
            
        Returns:
            List of inactive users
        """
        users = self.user_repo.get_inactive_users(days)
        
        return [UserSchema.from_orm(user) for user in users]
    
    # ============================================================================
    # NOTIFICATIONS AND COMMUNICATION
    # ============================================================================
    
    def send_welcome_email(self, user_id: int) -> bool:
        """
        Send welcome email to user
        
        Args:
            user_id: User ID
            
        Returns:
            True if sent successfully, False if not found
        """
        user = self.user_repo.get(user_id)
        
        if not user:
            return False
        
        # TODO: Implement email sending
        # This would integrate with an email service
        # email_service.send_welcome_email(user.email, user.first_name)
        
        return True
    
    def send_password_reset_email(self, email: str) -> bool:
        """
        Send password reset email
        
        Args:
            email: User email
            
        Returns:
            True if sent successfully, False if user not found
        """
        user = self.user_repo.get_by_email(email.lower())
        
        if not user:
            return False
        
        # TODO: Implement email sending with reset token
        # token = generate_reset_token(user.id)
        # email_service.send_password_reset_email(user.email, token)
        
        return True
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    
    def _validate_user_access(self, user_id: int) -> bool:
        """
        Validate that user belongs to current tenant
        
        Args:
            user_id: User ID
            
        Returns:
            True if user belongs to tenant or is super admin, False otherwise
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return False
        
        # Super admins can access all users
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Otherwise check tenant
        return user.tenant_id == self.tenant_id