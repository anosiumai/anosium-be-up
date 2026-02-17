from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timedelta

from models.ai_lead import AILead, AIInteraction, LeadStatus, LeadSource
from repositories.base import BaseRepository

class AILeadRepository(BaseRepository[AILead]):
    """Repository for AI Lead operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(db, AILead, tenant_id, current_user_id)
    
    def get_with_interactions(self, lead_id: int) -> Optional[AILead]:
        """Get lead with all interactions"""
        query = self.db.query(AILead).options(
            joinedload(AILead.patient),
            joinedload(AILead.interactions),
            joinedload(AILead.appointments)
        )
        query = query.filter(AILead.id == lead_id)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_phone(self, phone: str) -> Optional[AILead]:
        """Get lead by phone number"""
        query = self.db.query(AILead).filter(AILead.phone == phone)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_email(self, email: str) -> Optional[AILead]:
        """Get lead by email"""
        query = self.db.query(AILead).filter(AILead.email == email)
        query = self._apply_tenant_filter(query)
        return query.first()
    
    def get_by_status(
        self,
        status: LeadStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[AILead]:
        """Get leads by status"""
        query = self.db.query(AILead).filter(AILead.status == status)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AILead.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_source(
        self,
        source: LeadSource,
        skip: int = 0,
        limit: int = 100
    ) -> List[AILead]:
        """Get leads by source"""
        query = self.db.query(AILead).filter(AILead.source == source)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AILead.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_assigned_to_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AILead]:
        """Get leads assigned to a user"""
        query = self.db.query(AILead).filter(AILead.assigned_to == user_id)
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AILead.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_unassigned_leads(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[AILead]:
        """Get unassigned leads"""
        query = self.db.query(AILead).filter(AILead.assigned_to.is_(None))
        query = self._apply_tenant_filter(query)
        
        return (
            query.order_by(desc(AILead.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_leads_requiring_followup(
        self,
        limit: int = 100
    ) -> List[AILead]:
        """Get leads that require follow-up"""
        now = datetime.utcnow()
        
        query = self.db.query(AILead).filter(
            and_(
                AILead.next_follow_up_at <= now,
                AILead.status.notin_([
                    LeadStatus.CONVERTED,
                    LeadStatus.LOST
                ])
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(AILead.next_follow_up_at).limit(limit).all()
    
    def get_new_leads(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[AILead]:
        """Get new leads from last N hours"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(AILead).filter(
            and_(
                AILead.created_at >= since,
                AILead.status == LeadStatus.NEW
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.order_by(desc(AILead.created_at)).limit(limit).all()
    
    def search_leads(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[AILead]:
        """Search leads by name, phone, or email"""
        query = self.db.query(AILead).filter(
            or_(
                AILead.name.ilike(f"%{search_term}%"),
                AILead.phone.ilike(f"%{search_term}%"),
                AILead.email.ilike(f"%{search_term}%")
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def count_by_status(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Count leads by status"""
        query = self.db.query(
            AILead.status,
            func.count(AILead.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(AILead.created_at >= from_date)
        
        if to_date:
            query = query.filter(AILead.created_at <= to_date)
        
        results = query.group_by(AILead.status).all()
        
        return {status.value: count for status, count in results}
    
    def count_by_source(self) -> Dict[str, int]:
        """Count leads by source"""
        query = self.db.query(
            AILead.source,
            func.count(AILead.id).label('count')
        )
        query = self._apply_tenant_filter(query)
        
        results = query.group_by(AILead.source).all()
        
        return {source.value: count for source, count in results}
    
    def get_conversion_rate(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> float:
        """Calculate lead conversion rate"""
        query = self.db.query(AILead)
        query = self._apply_tenant_filter(query)
        
        if from_date:
            query = query.filter(AILead.created_at >= from_date)
        
        if to_date:
            query = query.filter(AILead.created_at <= to_date)
        
        total_leads = query.count()
        converted_leads = query.filter(AILead.status == LeadStatus.CONVERTED).count()
        
        if total_leads == 0:
            return 0.0
        
        return (converted_leads / total_leads) * 100

class AIInteractionRepository(BaseRepository[AIInteraction]):
    """Repository for AI Interaction operations"""
    
    def __init__(
        self, 
        db: Session, 
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None
    ):
        super().__init__(db, AIInteraction, tenant_id, current_user_id)
    
    def get_by_lead(
        self,
        lead_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AIInteraction]:
        """Get interactions for a lead"""
        return (
            self.db.query(AIInteraction)
            .filter(AIInteraction.lead_id == lead_id)
            .order_by(AIInteraction.timestamp)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_recent_interactions(
        self,
        lead_id: int,
        limit: int = 10
    ) -> List[AIInteraction]:
        """Get recent interactions for a lead"""
        return (
            self.db.query(AIInteraction)
            .filter(AIInteraction.lead_id == lead_id)
            .order_by(desc(AIInteraction.timestamp))
            .limit(limit)
            .all()
        )
    
    def count_by_lead(self, lead_id: int) -> int:
        """Count total interactions for a lead"""
        return (
            self.db.query(func.count(AIInteraction.id))
            .filter(AIInteraction.lead_id == lead_id)
            .scalar()
        )