"""
Repositories package
"""

from repositories.base import BaseRepository
from repositories.tenant import TenantRepository
from repositories.user import UserRepository
from repositories.patient import PatientRepository
from repositories.doctor import DoctorRepository
from repositories.department import DepartmentRepository
from repositories.appointment import AppointmentRepository
from repositories.visit import VisitRepository
from repositories.service import ServiceRepository, PackageRepository  # ✅ PackageRepository is here
from repositories.billing import InvoiceRepository, PaymentRepository, VisitServiceRepository  # ❌ Remove PackageRepository from here
from repositories.ai_lead import AILeadRepository, AIInteractionRepository
from repositories.notification import (
    NotificationRepository,
    NotificationTemplateRepository,
    NotificationPreferenceRepository,
)
from repositories.audit import AuditLogRepository, DataAccessLogRepository
from repositories.analytics import DailyMetricsRepository, SystemHealthMetricRepository

__all__ = [
    "BaseRepository",
    "TenantRepository",
    "UserRepository",
    "PatientRepository",
    "DoctorRepository",
    "DepartmentRepository",
    "AppointmentRepository",
    "VisitRepository",
    "ServiceRepository",
    "PackageRepository",
    "InvoiceRepository",
    "PaymentRepository",
    "VisitServiceRepository",
    "AILeadRepository",
    "AIInteractionRepository",
    "NotificationRepository",
    "NotificationTemplateRepository",
    "NotificationPreferenceRepository",
    "AuditLogRepository",
    "DataAccessLogRepository",
    "DailyMetricsRepository",
    "SystemHealthMetricRepository",
]