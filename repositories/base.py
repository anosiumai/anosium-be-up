from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from datetime import datetime

from models.audit import AuditLog, AuditAction
from core.database import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    """
    Base repository with:
    - Tenant isolation
    - Automatic audit logging
    - Soft deletes
    - Performance optimization
    - Common CRUD operations
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
        if hasattr(self.model, 'tenant_id') and self.tenant_id is not None:
            return query.filter(self.model.tenant_id == self.tenant_id)
        return query
    
    def _log_audit(
        self, 
        action: AuditAction, 
        resource_id: int,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None
    ):
        """Log audit trail for compliance"""
        if not self.tenant_id:
            return
        
        try:
            audit_log = AuditLog(
                tenant_id=self.tenant_id,
                user_id=self.current_user_id,
                action=action,
                resource_type=self.model.__tablename__,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                changes_summary=changes_summary,
                created_at=datetime.utcnow()
            )
            self.db.add(audit_log)
            self.db.flush()
        except Exception as e:
            # Log error but don't fail the main operation
            print(f"Audit log error: {str(e)}")
    
    def get(self, id: int) -> Optional[ModelType]:
        """Get single record by ID with tenant isolation"""
        query = self.db.query(self.model).filter(self.model.id == id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[ModelType]:
        """Get multiple records with filtering and pagination"""
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)
        
        # Apply is_active filter by default
        if hasattr(self.model, 'is_active') and not include_inactive:
            query = query.filter(self.model.is_active == True)
        
        # Apply custom filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)
        
        # Apply ordering
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(desc(getattr(self.model, order_by[1:])))
            else:
                query = query.order_by(getattr(self.model, order_by))
        else:
            # Default ordering by created_at if available
            if hasattr(self.model, 'created_at'):
                query = query.order_by(desc(self.model.created_at))
        
        return query.offset(skip).limit(limit).all()
    
    def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
        include_inactive: bool = False
    ) -> int:
        """Count records with optional filtering"""
        query = self.db.query(func.count(self.model.id))
        query = self._apply_tenant_filter(query)
        
        if hasattr(self.model, 'is_active') and not include_inactive:
            query = query.filter(self.model.is_active == True)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.scalar()
    
    def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Create record with automatic tenant assignment and audit"""
        # Auto-assign tenant_id
        if hasattr(self.model, 'tenant_id') and 'tenant_id' not in obj_in and self.tenant_id:
            obj_in['tenant_id'] = self.tenant_id
        
        # Auto-assign created_by
        if hasattr(self.model, 'created_by') and 'created_by' not in obj_in and self.current_user_id:
            obj_in['created_by'] = self.current_user_id
        
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.flush()
        self.db.refresh(db_obj)
        
        # Log audit
        self._log_audit(
            AuditAction.CREATE, 
            db_obj.id, 
            new_values=obj_in,
            changes_summary=f"Created {self.model.__tablename__} with ID {db_obj.id}"
        )
        
        return db_obj
    
    def update(
        self, 
        id: int, 
        obj_in: Dict[str, Any],
        skip_audit: bool = False
    ) -> Optional[ModelType]:
        """Update record with audit trail"""
        db_obj = self.get(id)
        if not db_obj:
            return None
        
        # Capture old values for audit
        old_values = {}
        for key in obj_in.keys():
            if hasattr(db_obj, key):
                old_values[key] = getattr(db_obj, key)
        
        # Update fields
        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        
        # Auto-update updated_at
        if hasattr(db_obj, 'updated_at'):
            db_obj.updated_at = datetime.utcnow()
        
        self.db.flush()
        self.db.refresh(db_obj)
        
        # Log audit
        if not skip_audit:
            changes = [f"{k}: {old_values.get(k)} → {v}" for k, v in obj_in.items()]
            self._log_audit(
                AuditAction.UPDATE, 
                id, 
                old_values=old_values, 
                new_values=obj_in,
                changes_summary=f"Updated {', '.join(changes)}"
            )
        
        return db_obj
    
    def delete(self, id: int, soft: bool = True) -> bool:
        """Delete record (soft delete by default)"""
        db_obj = self.get(id)
        if not db_obj:
            return False
        
        if soft and hasattr(db_obj, 'is_active'):
            # Soft delete
            db_obj.is_active = False
            if hasattr(db_obj, 'updated_at'):
                db_obj.updated_at = datetime.utcnow()
            self.db.flush()
            
            self._log_audit(
                AuditAction.DELETE, 
                id,
                changes_summary=f"Soft deleted {self.model.__tablename__} with ID {id}"
            )
        else:
            # Hard delete
            self._log_audit(
                AuditAction.DELETE, 
                id,
                changes_summary=f"Hard deleted {self.model.__tablename__} with ID {id}"
            )
            self.db.delete(db_obj)
            self.db.flush()
        
        return True
    
    def exists(self, id: int) -> bool:
        """Check if record exists"""
        query = self.db.query(self.model.id).filter(self.model.id == id)
        query = self._apply_tenant_filter(query)
        return query.first() is not None
    
    def bulk_create(self, objs_in: List[Dict[str, Any]]) -> List[ModelType]:
        """Bulk create records"""
        db_objs = []
        
        for obj_in in objs_in:
            if hasattr(self.model, 'tenant_id') and 'tenant_id' not in obj_in and self.tenant_id:
                obj_in['tenant_id'] = self.tenant_id
            
            db_obj = self.model(**obj_in)
            db_objs.append(db_obj)
        
        self.db.bulk_save_objects(db_objs)
        self.db.flush()
        
        return db_objs
    
    def search(
        self,
        search_term: str,
        search_fields: List[str],
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Full-text search across specified fields
        
        Args:
            search_term: Term to search for
            search_fields: List of field names to search in
            skip: Pagination offset
            limit: Maximum results
        """
        query = self.db.query(self.model)
        query = self._apply_tenant_filter(query)
        
        # Build OR conditions for search
        search_conditions = []
        for field in search_fields:
            if hasattr(self.model, field):
                field_obj = getattr(self.model, field)
                search_conditions.append(field_obj.ilike(f"%{search_term}%"))
        
        if search_conditions:
            query = query.filter(or_(*search_conditions))
        
        return query.offset(skip).limit(limit).all()