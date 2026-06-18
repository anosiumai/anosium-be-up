"""
Notification Service
====================

Handles creation, template rendering, preference gating, and delivery of
notifications across all channels.

EMAIL channel delivery is now implemented via `core.email.dispatch_email`
(previously a no-op / TODO). All other channels (SMS, WhatsApp, PUSH, IN_APP)
retain their existing stub behaviour and can be wired to real providers
independently without touching this file.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, time

from sqlalchemy.orm import Session
from sqlalchemy import desc

try:
    import pytz
except ImportError:
    pytz = None  # type: ignore[assignment]

from models.notification import (
    Notification,
    NotificationTemplate,
    NotificationPreference,
    NotificationType,
    NotificationChannel,
    NotificationStatus,
)
from models.patient import Patient
from models.user import User
from models.ai_lead import AILead, LeadStatus
from schemas.notification import (
    NotificationCreate,
    BulkNotificationCreate,
    NotificationTemplateCreate,
    NotificationPreferenceUpdate,
    NotificationPreference as NotificationPreferenceSchema,
)
from repositories.notification import (
    NotificationRepository,
    NotificationTemplateRepository,
    NotificationPreferenceRepository,
)
from core.email import dispatch_email

logger = logging.getLogger(__name__)

_CONTACTLESS_CHANNELS = {NotificationChannel.IN_APP, NotificationChannel.PUSH}


class _SafeDict(dict):
    """``str.format_map`` wrapper that leaves unresolved ``{keys}`` untouched."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class NotificationService:
    """
    Service layer for the notification sub-system.

    Responsibilities
    ----------------
    * Template resolution & variable interpolation
    * Per-recipient preference gating (channel enabled? type enabled? quiet hours?)
    * Single and bulk notification dispatch (persist + channel delivery)
    * User-preference upsert (read-with-defaults / partial update)

    Channel delivery
    ----------------
    EMAIL  → `core.email.dispatch_email("generic_notification", ...)`
    SMS    → stub (wire to Twilio/AWS SNS when ready)
    WA     → stub (wire to WhatsApp Business API when ready)
    PUSH   → stub (wire to FCM/APNs when ready)
    IN_APP → record in DB; frontend polls / uses WebSocket
    """

    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int] = None,
        current_user_id: Optional[int] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.current_user_id = current_user_id

        self.notification_repo = NotificationRepository(db, tenant_id, current_user_id)
        self.template_repo = NotificationTemplateRepository(db, tenant_id, current_user_id)
        self.preference_repo = NotificationPreferenceRepository(db, tenant_id, current_user_id)

    # ==================================================================
    # template rendering
    # ==================================================================

    def _resolve_template(
        self,
        template_id: str,
        variables: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Render a notification template and return ``{subject, message}``."""
        template = self.template_repo.get_by_code(template_id)
        if not template:
            raise ValueError(f"Notification template '{template_id}' not found")
        if not template.is_active:
            raise ValueError(f"Notification template '{template_id}' is not active")

        safe_vars = _SafeDict(variables or {})
        rendered_body = template.body_template.format_map(safe_vars)
        rendered_subject = (
            template.subject_template.format_map(safe_vars)
            if template.subject_template
            else None
        )
        return {"subject": rendered_subject, "message": rendered_body}

    # ==================================================================
    # preference helpers
    # ==================================================================

    def _get_preferences(
        self, user_id: Optional[int], patient_id: Optional[int]
    ) -> Optional[NotificationPreference]:
        if user_id:
            return self.preference_repo.get_by_user(user_id)
        if patient_id:
            return self.preference_repo.get_by_patient(patient_id)
        return None

    @staticmethod
    def _is_channel_enabled(
        prefs: Optional[NotificationPreference], channel: NotificationChannel
    ) -> bool:
        if prefs is None:
            return True
        _CHANNEL_FLAG = {
            NotificationChannel.EMAIL: "email_enabled",
            NotificationChannel.SMS: "sms_enabled",
            NotificationChannel.WHATSAPP: "whatsapp_enabled",
            NotificationChannel.PUSH: "push_enabled",
            NotificationChannel.IN_APP: True,
        }
        flag = _CHANNEL_FLAG.get(channel, True)
        if flag is True:
            return True
        return getattr(prefs, flag, True)

    @staticmethod
    def _is_type_enabled(
        prefs: Optional[NotificationPreference], notif_type: NotificationType
    ) -> bool:
        if prefs is None:
            return True
        enabled_types: Dict[str, bool] = prefs.enabled_types or {}
        return enabled_types.get(notif_type.value, True)

    @staticmethod
    def _is_within_quiet_hours(prefs: Optional[NotificationPreference]) -> bool:
        if prefs is None:
            return False
        start: Optional[time] = prefs.quiet_hours_start
        end: Optional[time] = prefs.quiet_hours_end
        if start is None or end is None:
            return False
        tz_name = prefs.timezone or "UTC"
        if pytz:
            try:
                tz = pytz.timezone(tz_name)
                now_local = datetime.now(tz).time()
            except pytz.exceptions.UnknownTimeZoneError:
                now_local = datetime.utcnow().time()
        else:
            now_local = datetime.utcnow().time()
        if start < end:
            return start <= now_local <= end
        return now_local >= start or now_local <= end

    # ==================================================================
    # contact-info resolution
    # ==================================================================

    def _resolve_contact_info(
        self,
        user_id: Optional[int],
        patient_id: Optional[int],
        channel: NotificationChannel,
        explicit_email: Optional[str],
        explicit_phone: Optional[str],
    ) -> Dict[str, Optional[str]]:
        if channel in _CONTACTLESS_CHANNELS:
            return {"email": None, "phone": None}

        email = explicit_email
        phone = explicit_phone

        if not email or not phone:
            source = None
            if user_id:
                source = self.db.query(User).filter(User.id == user_id).first()
            elif patient_id:
                source = self.db.query(Patient).filter(Patient.id == patient_id).first()

            if source:
                if not email and hasattr(source, "email"):
                    email = source.email
                if not phone and hasattr(source, "phone"):
                    phone = source.phone

        return {"email": email, "phone": phone}

    # ==================================================================
    # channel delivery
    # ==================================================================

    def _deliver(
        self,
        notification: Notification,
        subject: Optional[str],
        message: str,
        contact: Dict[str, Optional[str]],
    ) -> None:
        """
        Attempt actual delivery for the notification's channel.

        EMAIL
        -----
        Delegates to `core.email.dispatch_email("generic_notification", ...)`.
        This either enqueues a Celery task (async, non-blocking) or sends
        inline when Celery isn't configured.  Either way it never raises.

        SMS / WhatsApp / Push
        ---------------------
        Stubs — log a warning and leave status as PENDING.  Wire these to
        Twilio / WA Business API / FCM when ready; the pattern is identical
        to what EMAIL does here.

        IN_APP
        ------
        No delivery needed — the row in the DB *is* the notification.
        The frontend reads it via GET /notifications/me.

        Status updates
        --------------
        On successful delivery the notification's ``status`` is moved to
        ``SENT`` and ``sent_at`` is stamped.  On failure the status stays
        ``PENDING`` so the background worker can retry.  IN_APP is always
        considered "delivered" immediately.
        """
        channel = notification.channel

        if channel == NotificationChannel.EMAIL:
            email = contact.get("email")
            if not email:
                logger.warning(
                    "Cannot deliver EMAIL notification id=%s — no email address resolved",
                    notification.id,
                )
                notification.error_message = "No email address available for recipient"
                return

            # Resolve recipient name for a friendlier "Hi {name}" greeting.
            recipient_name: Optional[str] = None
            if notification.user_id:
                user = self.db.query(User).filter(User.id == notification.user_id).first()
                if user:
                    recipient_name = user.full_name
            elif notification.patient_id:
                patient = self.db.query(Patient).filter(Patient.id == notification.patient_id).first()
                if patient:
                    recipient_name = patient.full_name

            sent = dispatch_email(
                "generic_notification",
                to_email=email,
                subject=subject or notification.type.value.replace("_", " ").title(),
                message=message,
                recipient_name=recipient_name,
            )

            if sent:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
            else:
                # dispatch_email returns False when SMTP isn't configured or
                # the inline send failed. Leave as PENDING for retry.
                notification.error_message = "Email delivery failed or SMTP not configured"

        elif channel == NotificationChannel.SMS:
            # TODO: wire to Twilio / AWS SNS
            # from services.sms_service import dispatch_sms
            # sent = dispatch_sms(to_phone=contact["phone"], message=message)
            logger.warning(
                "SMS channel not yet implemented for notification id=%s", notification.id
            )
            notification.error_message = "SMS delivery not yet implemented"

        elif channel == NotificationChannel.WHATSAPP:
            # TODO: wire to WhatsApp Business API
            logger.warning(
                "WhatsApp channel not yet implemented for notification id=%s", notification.id
            )
            notification.error_message = "WhatsApp delivery not yet implemented"

        elif channel == NotificationChannel.PUSH:
            # TODO: wire to FCM / APNs
            logger.warning(
                "Push channel not yet implemented for notification id=%s", notification.id
            )
            notification.error_message = "Push delivery not yet implemented"

        elif channel == NotificationChannel.IN_APP:
            # The DB row *is* the in-app notification — nothing more to do.
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()

    # ==================================================================
    # single notification
    # ==================================================================

    def send_notification(self, notification_in: NotificationCreate) -> Notification:
        """
        Persist a single notification and attempt channel delivery.

        Flow
        ----
        1. Validate recipient identifier.
        2. Render template if ``template_id`` is set.
        3. Resolve contact info (email / phone).
        4. Gate against preferences (channel, type, quiet hours).
        5. Persist the row.
        6. If not blocked/scheduled, call ``_deliver()`` which handles EMAIL
           inline or via Celery and stubs for other channels.
        7. Commit and return.
        """
        if not notification_in.user_id and not notification_in.patient_id:
            raise ValueError("At least one of user_id or patient_id must be provided")

        subject = notification_in.subject
        message = notification_in.message

        if notification_in.template_id:
            rendered = self._resolve_template(
                notification_in.template_id,
                notification_in.template_variables,
            )
            subject = rendered["subject"] or subject
            message = rendered["message"]

        contact = self._resolve_contact_info(
            user_id=notification_in.user_id,
            patient_id=notification_in.patient_id,
            channel=notification_in.channel,
            explicit_email=notification_in.recipient_email,
            explicit_phone=notification_in.recipient_phone,
        )

        # --- preference gate ------------------------------------------
        prefs = self._get_preferences(notification_in.user_id, notification_in.patient_id)
        blocked_reason: Optional[str] = None

        if not self._is_channel_enabled(prefs, notification_in.channel):
            blocked_reason = (
                f"Channel '{notification_in.channel.value}' is disabled in recipient preferences"
            )
        elif not self._is_type_enabled(prefs, notification_in.type):
            blocked_reason = (
                f"Notification type '{notification_in.type.value}' is disabled in recipient preferences"
            )
        elif self._is_within_quiet_hours(prefs):
            blocked_reason = "Recipient is within quiet hours"

        # Determine whether this is a future-scheduled notification
        is_scheduled_future = bool(
            notification_in.scheduled_for
            and notification_in.scheduled_for > datetime.utcnow()
        )

        initial_status = (
            NotificationStatus.PENDING  # blocked or future-scheduled — deliver later
            if (blocked_reason or is_scheduled_future)
            else NotificationStatus.PENDING  # will be updated by _deliver() below
        )

        notification = Notification(
            tenant_id=self.tenant_id,
            user_id=notification_in.user_id,
            patient_id=notification_in.patient_id,
            type=notification_in.type,
            channel=notification_in.channel,
            subject=subject,
            message=message,
            template_id=notification_in.template_id,
            template_variables=notification_in.template_variables or {},
            recipient_email=contact["email"],
            recipient_phone=contact["phone"],
            status=initial_status,
            scheduled_for=notification_in.scheduled_for,
            error_message=blocked_reason,
            metadata=notification_in.metadata or {},
        )

        self.db.add(notification)
        self.db.flush()  # get notification.id before _deliver reads it

        if not blocked_reason and not is_scheduled_future:
            self._deliver(notification, subject, message, contact)

        if blocked_reason:
            logger.info(
                "Notification blocked for user_id=%s patient_id=%s: %s",
                notification_in.user_id,
                notification_in.patient_id,
                blocked_reason,
            )

        self.db.commit()
        self.db.refresh(notification)
        return notification

    # ==================================================================
    # bulk notifications
    # ==================================================================

    def send_bulk_notifications(self, bulk_in: BulkNotificationCreate) -> int:
        """
        Resolve recipients and dispatch one notification per recipient.
        Returns the number of notification rows persisted.
        """
        template = self.template_repo.get_by_code(bulk_in.template_id)
        if not template:
            raise ValueError(f"Template '{bulk_in.template_id}' not found")
        if not template.is_active:
            raise ValueError(f"Template '{bulk_in.template_id}' is not active")

        recipients = self._resolve_bulk_recipients(bulk_in.recipient_filters)
        if not recipients:
            raise ValueError("No recipients matched the provided filters")

        count = 0
        for recipient in recipients:
            notif_in = NotificationCreate(
                type=bulk_in.type,
                channel=bulk_in.channel,
                message="",
                user_id=recipient.get("user_id"),
                patient_id=recipient.get("patient_id"),
                recipient_email=recipient.get("email"),
                recipient_phone=recipient.get("phone"),
                scheduled_for=bulk_in.scheduled_for,
                template_id=bulk_in.template_id,
                template_variables=recipient.get("template_variables", {}),
            )
            self.send_notification(notif_in)
            count += 1

        return count

    def _resolve_bulk_recipients(
        self, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        recipients: List[Dict[str, Any]] = []
        handled_keys = {"patient_ids", "lead_status"}

        if "patient_ids" in filters:
            patients = (
                self.db.query(Patient)
                .filter(
                    Patient.id.in_(filters["patient_ids"]),
                    Patient.tenant_id == self.tenant_id,
                )
                .all()
            )
            for p in patients:
                recipients.append({
                    "patient_id": p.id,
                    "user_id": None,
                    "email": p.email,
                    "phone": p.phone,
                    "template_variables": {"patient_name": p.full_name},
                })

        if "lead_status" in filters:
            try:
                target_status = LeadStatus(filters["lead_status"])
            except ValueError:
                raise ValueError(
                    f"Invalid lead_status '{filters['lead_status']}'. "
                    f"Valid values: {[s.value for s in LeadStatus]}"
                )
            leads = (
                self.db.query(AILead)
                .filter(
                    AILead.status == target_status,
                    AILead.tenant_id == self.tenant_id,
                )
                .all()
            )
            for lead in leads:
                recipients.append({
                    "patient_id": lead.patient_id,
                    "user_id": None,
                    "email": lead.email,
                    "phone": lead.phone,
                    "template_variables": {"patient_name": lead.name},
                })

        unknown_keys = set(filters.keys()) - handled_keys
        if unknown_keys:
            logger.warning("Unrecognised recipient_filters keys ignored: %s", unknown_keys)

        return recipients

    # ==================================================================
    # read
    # ==================================================================

    def get_notifications(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        filters = filters or {}
        query = self.db.query(Notification).filter(
            Notification.tenant_id == self.tenant_id
        )
        if "type" in filters:
            query = query.filter(Notification.type == filters["type"])
        if "status" in filters:
            query = query.filter(Notification.status == filters["status"])

        total = query.count()
        items = (
            query.order_by(desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {"items": items, "total": total}

    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 20,
    ) -> List[Notification]:
        return self.notification_repo.get_by_user(
            user_id, limit=limit, unread_only=unread_only
        )

    # ==================================================================
    # read-status mutations
    # ==================================================================

    def mark_as_read(self, notification_id: int) -> bool:
        success = self.notification_repo.mark_as_read(notification_id)
        if success:
            self.db.commit()
        return success

    def mark_all_as_read(self, user_id: int) -> int:
        count = self.notification_repo.mark_all_as_read(user_id)
        self.db.commit()
        return count

    # ==================================================================
    # templates
    # ==================================================================

    def create_template(
        self, template_in: NotificationTemplateCreate
    ) -> NotificationTemplate:
        existing = self.template_repo.get_by_code(template_in.code)
        if existing:
            raise ValueError(
                f"A template with code '{template_in.code}' already exists in this tenant"
            )
        template = NotificationTemplate(
            tenant_id=self.tenant_id,
            code=template_in.code,
            name=template_in.name,
            description=template_in.description,
            type=template_in.type,
            channel=template_in.channel,
            subject_template=template_in.subject_template,
            body_template=template_in.body_template,
            language=template_in.language,
            is_active=True,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_templates(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[NotificationTemplate]:
        filters = filters or {}
        if filters.get("is_active", True):
            return self.template_repo.get_active_templates()
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.tenant_id == self.tenant_id
        )
        return query.all()

    # ==================================================================
    # preferences (upsert)
    # ==================================================================

    def get_user_preferences(self, user_id: int) -> NotificationPreferenceSchema:
        prefs = self.preference_repo.get_by_user(user_id)
        if prefs is None:
            return NotificationPreferenceSchema()
        return NotificationPreferenceSchema.model_validate(prefs)

    def update_user_preferences(
        self, user_id: int, prefs_in: NotificationPreferenceUpdate
    ) -> NotificationPreferenceSchema:
        prefs = self.preference_repo.get_by_user(user_id)
        update_data = prefs_in.model_dump(exclude_unset=True)

        if prefs is None:
            prefs = NotificationPreference(
                user_id=user_id,
                email_enabled=True,
                sms_enabled=True,
                whatsapp_enabled=True,
                push_enabled=True,
                enabled_types={
                    "appointment_reminder": True,
                    "payment_due": True,
                    "marketing": False,
                },
                timezone="UTC",
            )
            self.db.add(prefs)

        for key, value in update_data.items():
            setattr(prefs, key, value)

        self.db.commit()
        self.db.refresh(prefs)
        return NotificationPreferenceSchema.model_validate(prefs)