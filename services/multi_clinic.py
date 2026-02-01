"""
Multi-Clinic Service Layer
Handles tenant isolation, clinic management, and subscription features
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import secrets
import string

from models.clinic import Clinic
from models.user import User
from models.patient import Patient
from models.appointment import Appointment
from models.invoice import Invoice
from models.lead import Lead  # Now this will work
from models.base import SubscriptionTier, SubscriptionStatus, UserRole
from schemas.clinic import ClinicCreate, ClinicUpdate, ClinicResponse, ClinicStats


class MultiClinicService:
    """Service for managing multi-clinic/multi-tenant operations"""
    
    @staticmethod
    def generate_clinic_code() -> str:
        """Generate unique clinic code"""
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    
    @staticmethod
    def create_clinic(db: Session, clinic_data: ClinicCreate) -> Clinic:
        """
        Create a new clinic with default settings
        """
        clinic_code = MultiClinicService.generate_clinic_code()
        
        # Ensure unique clinic code
        while db.query(Clinic).filter(Clinic.clinic_code == clinic_code).first():
            clinic_code = MultiClinicService.generate_clinic_code()
        
        clinic = Clinic(
            clinic_code=clinic_code,
            name=clinic_data.name,
            email=clinic_data.email,
            phone=clinic_data.phone,
            address=clinic_data.address,
            logo_url=clinic_data.logo_url,
            primary_color=clinic_data.primary_color,
            secondary_color=clinic_data.secondary_color,
            subscription_tier=clinic_data.subscription_tier,
            subscription_status=SubscriptionStatus.TRIAL,
            subscription_start=datetime.utcnow(),
            subscription_end=datetime.utcnow() + timedelta(days=14),  # 14-day trial
            features={
                "ai_automation": clinic_data.subscription_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
                "advanced_billing": clinic_data.subscription_tier in [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
                "analytics": clinic_data.subscription_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
                "whatsapp_integration": clinic_data.subscription_tier == SubscriptionTier.ENTERPRISE,
                "max_doctors": 2 if clinic_data.subscription_tier == SubscriptionTier.FREE else (
                    5 if clinic_data.subscription_tier == SubscriptionTier.BASIC else (
                        15 if clinic_data.subscription_tier == SubscriptionTier.PREMIUM else 999
                    )
                ),
                "max_patients": 50 if clinic_data.subscription_tier == SubscriptionTier.FREE else (
                    200 if clinic_data.subscription_tier == SubscriptionTier.BASIC else (
                        1000 if clinic_data.subscription_tier == SubscriptionTier.PREMIUM else 999999
                    )
                )
            },
            ai_config={
                "enabled": False,
                "auto_respond": False,
                "lead_capture": True,
                "appointment_booking": False,
                "response_tone": "professional",
                "working_hours": {
                    "start": "09:00",
                    "end": "18:00",
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
                }
            }
        )
        
        db.add(clinic)
        db.commit()
        db.refresh(clinic)
        
        return clinic
    
    @staticmethod
    def get_clinic_by_id(db: Session, clinic_id: int) -> Optional[Clinic]:
        """Get clinic by ID"""
        return db.query(Clinic).filter(
            and_(Clinic.id == clinic_id, Clinic.is_active == True)
        ).first()
    
    @staticmethod
    def get_clinic_by_code(db: Session, clinic_code: str) -> Optional[Clinic]:
        """Get clinic by code"""
        return db.query(Clinic).filter(
            and_(Clinic.clinic_code == clinic_code, Clinic.is_active == True)
        ).first()
    
    @staticmethod
    def update_clinic(db: Session, clinic_id: int, clinic_data: ClinicUpdate) -> Optional[Clinic]:
        """Update clinic information"""
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            return None
        
        update_data = clinic_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(clinic, field, value)
        
        clinic.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(clinic)
        
        return clinic
    
    @staticmethod
    def get_clinic_stats(db: Session, clinic_id: int) -> ClinicStats:
        """Get comprehensive clinic statistics"""
        
        # Total patients
        total_patients = db.query(func.count(Patient.id)).filter(
            and_(Patient.clinic_id == clinic_id, Patient.is_active == True)
        ).scalar()
        
        # Total appointments
        total_appointments = db.query(func.count(Appointment.id)).filter(
            Appointment.clinic_id == clinic_id
        ).scalar()
        
        # Total revenue (from paid invoices)
        total_revenue = db.query(func.sum(Invoice.paid_amount)).filter(
            Invoice.clinic_id == clinic_id
        ).scalar() or 0.0
        
        # Pending invoices
        pending_invoices = db.query(func.count(Invoice.id)).filter(
            and_(
                Invoice.clinic_id == clinic_id,
                Invoice.balance_amount > 0
            )
        ).scalar()
        
        # Active leads
        active_leads = db.query(func.count(Lead.id)).filter(
            and_(
                Lead.clinic_id == clinic_id,
                Lead.status.in_(['new', 'contacted', 'qualified'])
            )
        ).scalar()
        
        # Conversion rate (leads to patients)
        total_leads = db.query(func.count(Lead.id)).filter(
            Lead.clinic_id == clinic_id
        ).scalar()
        
        converted_leads = db.query(func.count(Lead.id)).filter(
            and_(
                Lead.clinic_id == clinic_id,
                Lead.converted_to_patient == True
            )
        ).scalar()
        
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0.0
        
        return ClinicStats(
            total_patients=total_patients,
            total_appointments=total_appointments,
            total_revenue=total_revenue,
            pending_invoices=pending_invoices,
            active_leads=active_leads,
            conversion_rate=round(conversion_rate, 2)
        )
    
    @staticmethod
    def check_feature_access(clinic: Clinic, feature: str) -> bool:
        """
        Check if clinic has access to a specific feature
        """
        return clinic.features.get(feature, False)
    
    @staticmethod
    def check_limit(db: Session, clinic: Clinic, limit_type: str) -> Dict[str, Any]:
        """
        Check if clinic has reached its subscription limits
        Returns current usage and limit
        """
        if limit_type == "doctors":
            current = db.query(func.count(User.id)).filter(
                and_(
                    User.clinic_id == clinic.id,
                    User.role == UserRole.DOCTOR,
                    User.is_active == True
                )
            ).scalar()
            limit = clinic.features.get("max_doctors", 2)
            
        elif limit_type == "patients":
            current = db.query(func.count(Patient.id)).filter(
                and_(
                    Patient.clinic_id == clinic.id,
                    Patient.is_active == True
                )
            ).scalar()
            limit = clinic.features.get("max_patients", 50)
        else:
            return {"current": 0, "limit": 0, "can_add": False}
        
        return {
            "current": current,
            "limit": limit,
            "can_add": current < limit,
            "usage_percentage": round((current / limit * 100), 2) if limit > 0 else 0
        }
    
    @staticmethod
    def is_subscription_active(clinic: Clinic) -> bool:
        """Check if clinic subscription is active"""
        if clinic.subscription_status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
            return False
        
        if clinic.subscription_end and clinic.subscription_end < datetime.utcnow():
            return False
        
        return True
    
    @staticmethod
    def upgrade_subscription(
        db: Session, 
        clinic_id: int, 
        new_tier: SubscriptionTier,
        duration_days: int = 30
    ) -> Optional[Clinic]:
        """Upgrade clinic subscription"""
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            return None
        
        # Update tier
        clinic.subscription_tier = new_tier
        clinic.subscription_status = SubscriptionStatus.ACTIVE
        clinic.subscription_end = datetime.utcnow() + timedelta(days=duration_days)
        
        # Update features based on tier
        clinic.features.update({
            "ai_automation": new_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
            "advanced_billing": new_tier in [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
            "analytics": new_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
            "whatsapp_integration": new_tier == SubscriptionTier.ENTERPRISE,
            "max_doctors": 2 if new_tier == SubscriptionTier.FREE else (
                5 if new_tier == SubscriptionTier.BASIC else (
                    15 if new_tier == SubscriptionTier.PREMIUM else 999
                )
            ),
            "max_patients": 50 if new_tier == SubscriptionTier.FREE else (
                200 if new_tier == SubscriptionTier.BASIC else (
                    1000 if new_tier == SubscriptionTier.PREMIUM else 999999
                )
            )
        })
        
        clinic.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(clinic)
        
        return clinic
    
    @staticmethod
    def list_clinics(
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[Clinic]:
        """List all clinics with pagination"""
        query = db.query(Clinic)
        
        if is_active is not None:
            query = query.filter(Clinic.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def deactivate_clinic(db: Session, clinic_id: int) -> bool:
        """Soft delete a clinic"""
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            return False
        
        clinic.is_active = False
        clinic.updated_at = datetime.utcnow()
        db.commit()
        
        return True
    
    @staticmethod
    def get_expiring_subscriptions(db: Session, days: int = 7) -> List[Clinic]:
        """Get clinics with subscriptions expiring within specified days"""
        expiry_date = datetime.utcnow() + timedelta(days=days)
        
        return db.query(Clinic).filter(
            and_(
                Clinic.is_active == True,
                Clinic.subscription_end <= expiry_date,
                Clinic.subscription_end > datetime.utcnow()
            )
        ).all()