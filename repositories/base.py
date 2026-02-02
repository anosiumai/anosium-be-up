from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime
from app.models.audit import AuditLog, AuditAction
from app.core.security import get_current_user

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    """
    Base repository with:
    - Tenant isolation
    - Automatic audit logging
    - Soft deletes
    - Performance optimization
    """
    
    def __init__(
        self, 
        model: Type[ModelType], 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        self.model = model
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id
    
    def _apply_tenant_filter(self, query):
        """Apply tenant isolation automatically"""
        if hasattr(self.model, 'tenant_id') and self.tenant_id:
            return query.filter(self.model.tenant_id == self.tenant_id)
        return query
    
    def _log_audit(
        self, 
        action: AuditAction, 
        resource_id: int,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None
    ):
        """Log audit trail for compliance"""
        if not self.tenant_id:
            return
            
        audit_log = AuditLog(
            tenant_id=self.tenant_id,
            user_id=self.current_user_id,
            action=action,
            resource_type=self.model.__tablename__,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            created_at=datetime.utcnow()
        )
        self.db.add(audit_log)
        self.db.flush()
    
    def get(self, id: int) -> Optional[ModelType]:
        """Get single record with tenant isolation"""
        query = self.db.query(self.model).filter(self.model.id == id)
        query = self._apply_tenant_filter(query)
        
        # Log data access for HIPAA
        if self.model.__tablename__ in ['patients', 'visits']:
            # Log access
            pass
            
        return query.first()
    
    def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Get multiple records with filtering and pagination"""
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(desc(getattr(self.model, order_by[1:])))
            else:
                query = query.order_by(getattr(self.model, order_by))
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Create with automatic tenant assignment and audit"""
        if hasattr(self.model, 'tenant_id') and 'tenant_id' not in obj_in:
            obj_in['tenant_id'] = self.tenant_id
        
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.flush()
        
        self._log_audit(AuditAction.CREATE, db_obj.id, new_values=obj_in)
        
        return db_obj
    
    def update(self, id: int, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """Update with audit trail"""
        db_obj = self.get(id)
        if not db_obj:
            return None
        
        old_values = {k: getattr(db_obj, k) for k in obj_in.keys() if hasattr(db_obj, k)}
        
        for key, value in obj_in.items():
            setattr(db_obj, key, value)
        
        if hasattr(db_obj, 'updated_at'):
            db_obj.updated_at = datetime.utcnow()
        
        self.db.flush()
        self._log_audit(AuditAction.UPDATE, id, old_values=old_values, new_values=obj_in)
        
        return db_obj
    
    def delete(self, id: int, soft: bool = True) -> bool:
        """Delete with soft delete option"""
        db_obj = self.get(id)
        if not db_obj:
            return False
        
        if soft and hasattr(db_obj, 'is_active'):
            db_obj.is_active = False
            db_obj.updated_at = datetime.utcnow()
        else:
            self.db.delete(db_obj)
        
        self._log_audit(AuditAction.DELETE, id)
        self.db.flush()
        
        return True