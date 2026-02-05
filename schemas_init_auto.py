"""
Schemas Package - Pydantic Models
Auto-generated with correct imports based on actual file contents
"""

# ============================================================================
# TIER 1: Base models with NO dependencies on other schemas
# ============================================================================

from .tenant import TenantBase, TenantCreate, TenantUpdate, SubscriptionUpdate, TenantInDB, Tenant, TenantWithStats, Config
from .user import UserBase, UserCreate, UserUpdate, UserLogin, Token, TokenData, PasswordReset, PasswordChange, UserInDB, User, Config
from .patient import PatientBase, PatientCreate, PatientUpdate, PatientInDB, Patient, PatientSearch, PatientStats, PatientWithHistory, Config, Config

# Utility modules
try:
    from .common import *
except ImportError:
    pass

try:
    from .auth import *
except ImportError:
    pass

# ============================================================================
# TIER 2: Models with CIRCULAR dependencies (department ↔ doctor)
# ============================================================================

from .department import DepartmentBase, DepartmentCreate, DepartmentUpdate, DepartmentInDB, Department, DepartmentWithDoctors, Config
from .doctor import DoctorBase, DoctorCreate, DoctorUpdate, DoctorAvailability, DoctorInDB, Doctor, DoctorWithSchedule, DoctorStats, Config


# ============================================================================
# TIER 3: Models that depend on Tier 1 & 2
# ============================================================================

from .service import ServiceBase, ServiceCreate, ServiceUpdate, ServiceInDB, Service, PackageServiceItem, PackageBase, PackageCreate, PackageUpdate, PackageInDB, Package, PackageWithServices, ServiceStatistics, PackageStatistics, Config, Config, Config
from .appointment import AppointmentBase, AppointmentCreate, AppointmentUpdate, AppointmentReschedule, AppointmentCancel, AppointmentInDB, Appointment, AppointmentWithDetails, DoctorAvailabilitySlot, Config
from .visit import Vitals, Prescription, LabTest, VisitBase, VisitCreate, VisitUpdate, VisitInDB, Visit, VisitWithDetails, Config
from .billing import InvoiceItemCreate, InvoiceItem, InvoiceBase, InvoiceCreate, InvoiceUpdate, InvoiceInDB, Invoice, InvoiceWithItems, PaymentBase, PaymentCreate, PaymentInDB, Payment, PaymentSummary, Config, Config, Config
from .ai_lead import AIInteractionCreate, AIInteraction, AILeadBase, AILeadCreate, AILeadUpdate, LeadConversion, AILeadInDB, AILead, AILeadWithInteractions, Config, Config
from .notification import NotificationBase, NotificationCreate, BulkNotificationCreate, NotificationInDB, Notification, NotificationTemplateBase, NotificationTemplateCreate, NotificationTemplate, NotificationPreference, NotificationPreferenceUpdate, Config, Config, Config


# ============================================================================
# REBUILD FUNCTION
# ============================================================================

def rebuild_all_models():
    """Rebuild all Pydantic models to resolve forward references."""
    
    import sys
    current_module = sys.modules[__name__]
    
    # Collect all model classes from current module
    models = []
    for name in dir(current_module):
        obj = getattr(current_module, name)
        if isinstance(obj, type) and hasattr(obj, 'model_rebuild'):
            models.append(obj)
    
    print(f"\n🔧 Rebuilding {len(models)} Pydantic models...")
    print("=" * 70)
    
    failed = []
    for model in models:
        try:
            model.model_rebuild()
            print(f"   ✅ {model.__name__}")
        except Exception as e:
            failed.append((model.__name__, str(e)))
            print(f"   ⚠️  {model.__name__}: {str(e)[:60]}")
    
    print("=" * 70)
    if failed:
        print(f"⚠️  {len(failed)} model(s) failed to rebuild")
    else:
        print(f"✅ All {len(models)} models rebuilt successfully!")
    print("=" * 70 + "\n")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['rebuild_all_models']

# Add all classes to __all__
__all__.append('TenantBase')
__all__.append('TenantCreate')
__all__.append('TenantUpdate')
__all__.append('SubscriptionUpdate')
__all__.append('TenantInDB')
__all__.append('Tenant')
__all__.append('TenantWithStats')
__all__.append('Config')
__all__.append('UserBase')
__all__.append('UserCreate')
__all__.append('UserUpdate')
__all__.append('UserLogin')
__all__.append('Token')
__all__.append('TokenData')
__all__.append('PasswordReset')
__all__.append('PasswordChange')
__all__.append('UserInDB')
__all__.append('User')
__all__.append('Config')
__all__.append('PatientBase')
__all__.append('PatientCreate')
__all__.append('PatientUpdate')
__all__.append('PatientInDB')
__all__.append('Patient')
__all__.append('PatientSearch')
__all__.append('PatientStats')
__all__.append('PatientWithHistory')
__all__.append('Config')
__all__.append('Config')
__all__.append('DepartmentBase')
__all__.append('DepartmentCreate')
__all__.append('DepartmentUpdate')
__all__.append('DepartmentInDB')
__all__.append('Department')
__all__.append('DepartmentWithDoctors')
__all__.append('Config')
__all__.append('DoctorBase')
__all__.append('DoctorCreate')
__all__.append('DoctorUpdate')
__all__.append('DoctorAvailability')
__all__.append('DoctorInDB')
__all__.append('Doctor')
__all__.append('DoctorWithSchedule')
__all__.append('DoctorStats')
__all__.append('Config')
__all__.append('ServiceBase')
__all__.append('ServiceCreate')
__all__.append('ServiceUpdate')
__all__.append('ServiceInDB')
__all__.append('Service')
__all__.append('PackageServiceItem')
__all__.append('PackageBase')
__all__.append('PackageCreate')
__all__.append('PackageUpdate')
__all__.append('PackageInDB')
__all__.append('Package')
__all__.append('PackageWithServices')
__all__.append('ServiceStatistics')
__all__.append('PackageStatistics')
__all__.append('Config')
__all__.append('Config')
__all__.append('Config')
__all__.append('AppointmentBase')
__all__.append('AppointmentCreate')
__all__.append('AppointmentUpdate')
__all__.append('AppointmentReschedule')
__all__.append('AppointmentCancel')
__all__.append('AppointmentInDB')
__all__.append('Appointment')
__all__.append('AppointmentWithDetails')
__all__.append('DoctorAvailabilitySlot')
__all__.append('Config')
__all__.append('Vitals')
__all__.append('Prescription')
__all__.append('LabTest')
__all__.append('VisitBase')
__all__.append('VisitCreate')
__all__.append('VisitUpdate')
__all__.append('VisitInDB')
__all__.append('Visit')
__all__.append('VisitWithDetails')
__all__.append('Config')
__all__.append('InvoiceItemCreate')
__all__.append('InvoiceItem')
__all__.append('InvoiceBase')
__all__.append('InvoiceCreate')
__all__.append('InvoiceUpdate')
__all__.append('InvoiceInDB')
__all__.append('Invoice')
__all__.append('InvoiceWithItems')
__all__.append('PaymentBase')
__all__.append('PaymentCreate')
__all__.append('PaymentInDB')
__all__.append('Payment')
__all__.append('PaymentSummary')
__all__.append('Config')
__all__.append('Config')
__all__.append('Config')
__all__.append('AIInteractionCreate')
__all__.append('AIInteraction')
__all__.append('AILeadBase')
__all__.append('AILeadCreate')
__all__.append('AILeadUpdate')
__all__.append('LeadConversion')
__all__.append('AILeadInDB')
__all__.append('AILead')
__all__.append('AILeadWithInteractions')
__all__.append('Config')
__all__.append('Config')
__all__.append('NotificationBase')
__all__.append('NotificationCreate')
__all__.append('BulkNotificationCreate')
__all__.append('NotificationInDB')
__all__.append('Notification')
__all__.append('NotificationTemplateBase')
__all__.append('NotificationTemplateCreate')
__all__.append('NotificationTemplate')
__all__.append('NotificationPreference')
__all__.append('NotificationPreferenceUpdate')
__all__.append('Config')
__all__.append('Config')
__all__.append('Config')
