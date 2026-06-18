"""
Schemas Package - Pydantic Models
COMPLETE FIX with all nested models in namespace
"""
import logging
_log = logging.getLogger(__name__)

# ============================================================================
# TIER 1: Base models with NO dependencies on other schemas
# ============================================================================

from .tenant import (
    TenantBase, TenantCreate, TenantUpdate, SubscriptionUpdate, 
    TenantInDB, Tenant, TenantWithStats
)

from .user import (
    UserBase, UserCreate, UserUpdate, UserLogin, 
    Token, TokenData, PasswordReset, PasswordChange, 
    UserInDB, User
)

from .patient import (
    PatientBase, PatientCreate, PatientUpdate, PatientInDB, 
    Patient, PatientSearch, PatientStats, PatientWithHistory
)

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

from .department import (
    DepartmentBase, DepartmentCreate, DepartmentUpdate, 
    DepartmentInDB, Department, DepartmentWithDoctors
)

from .doctor import (
    DoctorBase, DoctorCreate, DoctorUpdate, DoctorAvailability, 
    DoctorInDB, Doctor, DoctorWithSchedule, DoctorStats
)


# ============================================================================
# TIER 3: Models that depend on Tier 1 & 2
# ============================================================================

from .service import (
    ServiceBase, ServiceCreate, ServiceUpdate, ServiceInDB, Service,
    PackageServiceItem, PackageBase, PackageCreate, PackageUpdate, 
    PackageInDB, Package, PackageWithServices, 
    ServiceStatistics, PackageStatistics
)

from .appointment import (
    AppointmentBase, AppointmentCreate, AppointmentUpdate, 
    AppointmentReschedule, AppointmentCancel, AppointmentInDB, 
    Appointment, AppointmentWithDetails, DoctorAvailabilitySlot
)

from .visit import (
    Vitals, Prescription, LabTest, 
    VisitBase, VisitCreate, VisitUpdate, 
    VisitInDB, Visit, VisitWithDetails
)

from .billing import (
    InvoiceItemCreate, InvoiceItem, InvoiceBase, InvoiceCreate, 
    InvoiceUpdate, InvoiceInDB, Invoice, InvoiceWithItems,
    PaymentBase, PaymentCreate, PaymentInDB, Payment, PaymentSummary
)

from .ai_lead import (
    AIInteractionCreate, AIInteraction, AILeadBase, AILeadCreate, 
    AILeadUpdate, LeadConversion, AILeadInDB, AILead, AILeadWithInteractions
)

from .notification import (
    NotificationBase, NotificationCreate, BulkNotificationCreate, 
    NotificationInDB, Notification, NotificationTemplateBase, 
    NotificationTemplateCreate, NotificationTemplate, 
    NotificationPreference, NotificationPreferenceUpdate
)


# ============================================================================
# REBUILD FUNCTION - COMPLETE FIX
# ============================================================================

def rebuild_all_models():
    """
    Rebuild all Pydantic models to resolve forward references.
    
    CRITICAL: The namespace must include EVERY model that appears in a 
    forward reference ANYWHERE in your schemas, including nested references.
    """
    
    failed_models = []
    
    # COMPLETE namespace with ALL models (including nested ones like InvoiceItem)
    namespace = {
        # Tier 1: Core entities
        'Tenant': Tenant,
        'TenantWithStats': TenantWithStats,
        'User': User,
        'Patient': Patient,
        'PatientWithHistory': PatientWithHistory,
        
        # Tier 2: Circular dependencies
        'Department': Department,
        'DepartmentWithDoctors': DepartmentWithDoctors,
        'Doctor': Doctor,
        'DoctorWithSchedule': DoctorWithSchedule,
        'DoctorStats': DoctorStats,
        
        # Tier 3: Services
        'Service': Service,
        'Package': Package,
        'PackageWithServices': PackageWithServices,
        'PackageServiceItem': PackageServiceItem,
        
        # Appointments
        'Appointment': Appointment,
        'AppointmentWithDetails': AppointmentWithDetails,
        
        # Visits
        'Visit': Visit,
        'VisitWithDetails': VisitWithDetails,
        'Vitals': Vitals,
        'Prescription': Prescription,
        'LabTest': LabTest,
        
        # Billing - CRITICAL: Include both Invoice AND InvoiceItem
        'Invoice': Invoice,
        'InvoiceWithItems': InvoiceWithItems,
        'InvoiceItem': InvoiceItem,  # This was likely missing!
        'Payment': Payment,
        'PaymentSummary': PaymentSummary,
        
        # AI Leads
        'AILead': AILead,
        'AILeadWithInteractions': AILeadWithInteractions,
        'AIInteraction': AIInteraction,
        
        # Notifications
        'Notification': Notification,
        'NotificationTemplate': NotificationTemplate,
        'NotificationPreference': NotificationPreference,
    }
    
    # TIER 1: Base models (no dependencies)
    tier1_models = [
        TenantBase, TenantCreate, TenantUpdate, TenantInDB, Tenant,
        UserBase, UserCreate, UserUpdate, UserInDB, User,
        PatientBase, PatientCreate, PatientUpdate, PatientInDB, Patient,
    ]
    
    for model in tier1_models:
        try:
            model.model_rebuild(_types_namespace=namespace)
           
        except Exception as e:
            failed_models.append((model.__name__, str(e)))
    
    # TIER 2: Circular dependencies (Department ↔ Doctor)
    tier2_models = [
        DepartmentBase, DepartmentCreate, DepartmentUpdate, DepartmentInDB, Department,
        DoctorBase, DoctorCreate, DoctorUpdate, DoctorInDB, Doctor,
    ]
    
    for model in tier2_models:
        try:
            model.model_rebuild(_types_namespace=namespace)
            _log.debug("Model rebuilt: %s", model.__name__)
        except Exception as e:
            failed_models.append((model.__name__, str(e)))
    
    # TIER 3: Complex relationships (including nested models)
    tier3_models = [
        # Services
        ServiceBase, ServiceCreate, ServiceUpdate, Service,
        PackageServiceItem, PackageBase, PackageCreate, Package,
        
        # Appointments
        AppointmentBase, AppointmentCreate, AppointmentUpdate, Appointment,
        
        # Visits
        Vitals, Prescription, LabTest,
        VisitBase, VisitCreate, VisitUpdate, Visit,
        
        # Billing - rebuild InvoiceItem first, then Invoice
        InvoiceItemCreate, InvoiceItem,
        InvoiceBase, InvoiceCreate, InvoiceUpdate, Invoice, InvoiceWithItems,
        PaymentBase, PaymentCreate, Payment,
        
        # AI
        AIInteractionCreate, AIInteraction,
        AILeadBase, AILeadCreate, AILeadUpdate, AILead,
        
        # Notifications
        NotificationBase, NotificationCreate, Notification,
        NotificationTemplateBase, NotificationTemplateCreate, NotificationTemplate,
    ]
    
    for model in tier3_models:
        try:
            model.model_rebuild(_types_namespace=namespace)
        except Exception as e:
            failed_models.append((model.__name__, str(e)))
    
    # Summary
    if failed_models:
        for name, error in failed_models:
            _log.warning("Model rebuild failed: %s — %s", name, error[:80])
    else:
        total = len(tier1_models) + len(tier2_models) + len(tier3_models)    


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Tenant
    'TenantBase', 'TenantCreate', 'TenantUpdate', 'SubscriptionUpdate',
    'TenantInDB', 'Tenant', 'TenantWithStats',
    
    # User
    'UserBase', 'UserCreate', 'UserUpdate', 'UserLogin',
    'Token', 'TokenData', 'PasswordReset', 'PasswordChange',
    'UserInDB', 'User',
    
    # Patient
    'PatientBase', 'PatientCreate', 'PatientUpdate', 'PatientInDB',
    'Patient', 'PatientSearch', 'PatientStats', 'PatientWithHistory',
    
    # Department
    'DepartmentBase', 'DepartmentCreate', 'DepartmentUpdate',
    'DepartmentInDB', 'Department', 'DepartmentWithDoctors',
    
    # Doctor
    'DoctorBase', 'DoctorCreate', 'DoctorUpdate', 'DoctorAvailability',
    'DoctorInDB', 'Doctor', 'DoctorWithSchedule', 'DoctorStats',
    
    # Service & Package
    'ServiceBase', 'ServiceCreate', 'ServiceUpdate', 'ServiceInDB', 'Service',
    'PackageServiceItem', 'PackageBase', 'PackageCreate', 'PackageUpdate',
    'PackageInDB', 'Package', 'PackageWithServices',
    'ServiceStatistics', 'PackageStatistics',
    
    # Appointment
    'AppointmentBase', 'AppointmentCreate', 'AppointmentUpdate',
    'AppointmentReschedule', 'AppointmentCancel', 'AppointmentInDB',
    'Appointment', 'AppointmentWithDetails', 'DoctorAvailabilitySlot',
    
    # Visit
    'Vitals', 'Prescription', 'LabTest',
    'VisitBase', 'VisitCreate', 'VisitUpdate',
    'VisitInDB', 'Visit', 'VisitWithDetails',
    
    # Billing
    'InvoiceItemCreate', 'InvoiceItem', 'InvoiceBase', 'InvoiceCreate',
    'InvoiceUpdate', 'InvoiceInDB', 'Invoice', 'InvoiceWithItems',
    'PaymentBase', 'PaymentCreate', 'PaymentInDB', 'Payment', 'PaymentSummary',
    
    # AI Leads
    'AIInteractionCreate', 'AIInteraction', 'AILeadBase', 'AILeadCreate',
    'AILeadUpdate', 'LeadConversion', 'AILeadInDB', 'AILead', 'AILeadWithInteractions',
    
    # Notifications
    'NotificationBase', 'NotificationCreate', 'BulkNotificationCreate',
    'NotificationInDB', 'Notification', 'NotificationTemplateBase',
    'NotificationTemplateCreate', 'NotificationTemplate',
    'NotificationPreference', 'NotificationPreferenceUpdate',
    
    # Rebuild function
    'rebuild_all_models',
]