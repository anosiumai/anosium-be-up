from typing import Optional
from sqlalchemy.orm import Session

class BaseService:
    """
    Base service class with common functionality
    """
    
    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id
    
    def commit(self):
        """Commit database transaction"""
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
    
    def rollback(self):
        """Rollback database transaction"""
        self.db.rollback()
    
    def refresh(self, obj):
        """Refresh object from database"""
        self.db.refresh(obj)