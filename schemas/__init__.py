from .tenant import (
    TenantBase, TenantCreate, TenantUpdate, TenantInDB, Tenant,
    TenantWithStats, SubscriptionUpdate
)
from .user import (
    UserBase, UserCreate, UserUpdate, UserInDB, User,
    UserLogin, Token, TokenData, PasswordReset, PasswordChange
)
from .patient import (
    PatientBase, PatientCreate, PatientUpdate, PatientInDB, Patient,
    PatientWithHistory, PatientSearch, PatientStats
)
from .doctor import (
    DoctorBase, DoctorCreate, DoctorUpdate, DoctorInDB, Doctor,
    DoctorAvailability, DoctorWithSchedule, DoctorStats
)
from .department import (
    DepartmentBase, DepartmentCreate, DepartmentUpdate, DepartmentInDB, Department,
    DepartmentWithDoctors
)
from .appointment import (
    AppointmentBase, AppointmentCreate, AppointmentUpdate, AppointmentInDB, Appointment,
    AppointmentWithDetails, AppointmentReschedule, AppointmentCancel,
    DoctorAvailabilitySlot
)
from .visit import (
    VisitBase, VisitCreate, VisitUpdate, VisitInDB, Visit,
    VisitWithDetails, Vitals, Prescription, LabTest
)
from .service import (
    ServiceBase, ServiceCreate, ServiceUpdate, ServiceInDB, Service,
    PackageBase, PackageCreate, PackageInDB, Package
)
from .billing import (
    InvoiceBase, InvoiceCreate, InvoiceUpdate, InvoiceInDB, Invoice,
    InvoiceWithItems, InvoiceItem, InvoiceItemCreate,
    PaymentBase, PaymentCreate, PaymentInDB, Payment,
    PaymentSummary
)
from .ai_lead import (
    AILeadBase, AILeadCreate, AILeadUpdate, AILeadInDB, AILead,
    AILeadWithInteractions, AIInteractionCreate, AIInteraction,
    LeadConversion
)
from .notification import (
    NotificationBase, NotificationCreate, NotificationInDB, Notification,
    NotificationTemplateBase, NotificationTemplateCreate, NotificationTemplate,
    NotificationPreference, NotificationPreferenceUpdate,
    BulkNotificationCreate
)
from .audit import (
    AuditLogBase, AuditLogInDB, AuditLog,
    DataAccessLogBase, DataAccessLogInDB, DataAccessLog
)
from .analytics import (
    DailyMetricsInDB, DailyMetrics, DashboardStats,
    RevenueReport, AppointmentReport, PatientReport
)
from .common import (
    PaginatedResponse, SuccessResponse, ErrorResponse,
    HealthCheck, FileUpload
)


def rebuild_all_models():
    """
    Rebuild all Pydantic models with forward references.
    
    This function should be called explicitly from main.py during application
    startup (in the lifespan function) to ensure all forward references are
    resolved before FastAPI generates OpenAPI documentation.
    
    DO NOT call this at module import time - it must be called after all
    routers are imported but before the application starts serving requests.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("🔧 Rebuilding Pydantic models with forward references...")
    
    # List all models that use forward references (string type hints)
    models_to_rebuild = [
        # Patient schemas
        PatientWithHistory,  # Has List['Visit'], List['Appointment']
        
        # Visit schemas (if they have forward refs to Patient)
        Visit,
        VisitWithDetails,
        
        # Appointment schemas (if they have forward refs to Patient)
        Appointment,
        AppointmentWithDetails,
        
        # Doctor schemas (if they have forward refs)
        DoctorWithSchedule,
        
        # Department schemas (if they have forward refs)
        DepartmentWithDoctors,
        
        # AI Lead schemas (if they have forward refs)
        AILeadWithInteractions,
        
        # Invoice schemas (if they have forward refs)
        InvoiceWithItems,
    ]
    
    success_count = 0
    for model in models_to_rebuild:
        try:
            model.model_rebuild()
            logger.debug(f"  ✅ Rebuilt: {model.__name__}")
            success_count += 1
        except Exception as e:
            # Log warning but continue - Pydantic v2 often auto-rebuilds on first use
            logger.debug(f"  ⚠️ Could not rebuild {model.__name__}: {e}")
    
    logger.info(f"✅ Successfully rebuilt {success_count}/{len(models_to_rebuild)} models")


__all__ = [
    # Tenant
    "TenantBase", "TenantCreate", "TenantUpdate", "TenantInDB", "Tenant",
    "TenantWithStats", "SubscriptionUpdate",
    
    # User
    "UserBase", "UserCreate", "UserUpdate", "UserInDB", "User",
    "UserLogin", "Token", "TokenData", "PasswordReset", "PasswordChange",
    
    # Patient
    "PatientBase", "PatientCreate", "PatientUpdate", "PatientInDB", "Patient",
    "PatientWithHistory", "PatientSearch", "PatientStats",
    
    # Doctor
    "DoctorBase", "DoctorCreate", "DoctorUpdate", "DoctorInDB", "Doctor",
    "DoctorAvailability", "DoctorWithSchedule", "DoctorStats",
    
    # Department
    "DepartmentBase", "DepartmentCreate", "DepartmentUpdate", "DepartmentInDB", "Department",
    "DepartmentWithDoctors",
    
    # Appointment
    "AppointmentBase", "AppointmentCreate", "AppointmentUpdate", "AppointmentInDB", "Appointment",
    "AppointmentWithDetails", "AppointmentReschedule", "AppointmentCancel",
    "DoctorAvailabilitySlot",
    
    # Visit
    "VisitBase", "VisitCreate", "VisitUpdate", "VisitInDB", "Visit",
    "VisitWithDetails", "Vitals", "Prescription", "LabTest",
    
    # Service
    "ServiceBase", "ServiceCreate", "ServiceUpdate", "ServiceInDB", "Service",
    "PackageBase", "PackageCreate", "PackageInDB", "Package",
    
    # Billing
    "InvoiceBase", "InvoiceCreate", "InvoiceUpdate", "InvoiceInDB", "Invoice",
    "InvoiceWithItems", "InvoiceItem", "InvoiceItemCreate",
    "PaymentBase", "PaymentCreate", "PaymentInDB", "Payment",
    "PaymentSummary",
    
    # AI Lead
    "AILeadBase", "AILeadCreate", "AILeadUpdate", "AILeadInDB", "AILead",
    "AILeadWithInteractions", "AIInteractionCreate", "AIInteraction",
    "LeadConversion",
    
    # Notification
    "NotificationBase", "NotificationCreate", "NotificationInDB", "Notification",
    "NotificationTemplateBase", "NotificationTemplateCreate", "NotificationTemplate",
    "NotificationPreference", "NotificationPreferenceUpdate",
    "BulkNotificationCreate",
    
    # Audit
    "AuditLogBase", "AuditLogInDB", "AuditLog",
    "DataAccessLogBase", "DataAccessLogInDB", "DataAccessLog",
    
    # Analytics
    "DailyMetricsInDB", "DailyMetrics", "DashboardStats",
    "RevenueReport", "AppointmentReport", "PatientReport",
    
    # Common
    "PaginatedResponse", "SuccessResponse", "ErrorResponse",
    "HealthCheck", "FileUpload",
    
    # Utility functions
    "rebuild_all_models",
]