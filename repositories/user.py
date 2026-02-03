from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta

from models.user import User, UserRole
from repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    """Repository for User operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(User, db, tenant_id, current_user_id)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        query = self.db.query(User).filter(User.email == email)
        # Don't apply tenant filter for email lookup (needed for login)
        return query.first()
    
    def check_email_exists(self, email: str, exclude_id: Optional[int] = None) -> bool:
        """Check if email already exists"""
        query = self.db.query(User).filter(User.email == email)
        
        if exclude_id:
            query = query.filter(User.id != exclude_id)
        
        return query.first() is not None
    
    def get_by_role(
        self, 
        role: UserRole,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Get users by role"""
        query = self.db.query(User).filter(User.role == role)
        query = self._apply_tenant_filter(query)
        
        return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get active users"""
        query = self.db.query(User).filter(User.is_active == True)
        query = self._apply_tenant_filter(query)
        
        return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    def search_users(
        self, 
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Search users by name or email"""
        query = self.db.query(User).filter(
            or_(
                User.first_name.ilike(f"%{search_term}%"),
                User.last_name.ilike(f"%{search_term}%"),
                User.email.ilike(f"%{search_term}%")
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp"""
        user = self.get(user_id)
        if not user:
            return False
        
        user.last_login = datetime.utcnow()
        self.db.flush()
        return True
    
    def count_by_role(self) -> Dict[str, int]:
        """Count users by role"""
        query = self.db.query(
            User.role,
            func.count(User.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        results = query.group_by(User.role).all()
        
        return {role.value: count for role, count in results}
    
    def get_recently_registered(self, days: int = 7, limit: int = 10) -> List[User]:
        """Get recently registered users"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(User).filter(User.created_at >= since_date)
        query = self._apply_tenant_filter(query)
        
        return query.order_by(User.created_at.desc()).limit(limit).all()
    
    def get_inactive_users(self, days: int = 30) -> List[User]:
        """Get users who haven't logged in for N days"""
        inactive_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(User).filter(
            or_(
                User.last_login < inactive_date,
                User.last_login.is_(None)
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.all()