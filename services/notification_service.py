import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import desc

try:
    import pytz
except ImportError:  # pragma: no cover – fallback so the module is importable
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Channels that do NOT require a phone / email address to deliver.
# ---------------------------------------------------------------------------
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
    * Single and bulk notification dispatch (persist + status bookkeeping)
    * User-preference upsert (read-with-defaults / partial update)
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
        """
        Look up a template by ``code``, interpolate *variables* into
        ``subject_template`` / ``body_template``, and return the rendered
        ``subject`` and ``message``.

        Uses ``_SafeDict`` so that any placeholder the caller forgot to
        supply is left as literal ``{placeholder}`` text rather than raising.
        """
        template = self.template_repo.get_by_code(template_id)
        if not template:
            raise ValueError(f"Notification template '{template_id}' not found or inactive")
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

    def _get_preferences(self, user_id: Optional[int], patient_id: Optional[int]) -> NotificationPreference:
        """
        Fetch the preference row for a user or patient.  Returns ``None``
        when no row exists (caller interprets as "all defaults enabled").
        """
        if user_id:
            return self.preference_repo.get_by_user(user_id)
        if patient_id:
            return self.preference_repo.get_by_patient(patient_id)
        return None

    @staticmethod
    def _is_channel_enabled(prefs: Optional[NotificationPreference], channel: NotificationChannel) -> bool:
        """Check whether the given channel is enabled in user prefs."""
        if prefs is None:
            return True  # no prefs row → all defaults on

        _CHANNEL_FLAG = {
            NotificationChannel.EMAIL: "email_enabled",
            NotificationChannel.SMS: "sms_enabled",
            NotificationChannel.WHATSAPP: "whatsapp_enabled",
            NotificationChannel.PUSH: "push_enabled",
            NotificationChannel.IN_APP: True,  # always allowed
        }
        flag = _CHANNEL_FLAG.get(channel, True)
        if flag is True:
            return True
        return getattr(prefs, flag, True)

    @staticmethod
    def _is_type_enabled(prefs: Optional[NotificationPreference], notif_type: NotificationType) -> bool:
        """Check whether the notification type is enabled in ``enabled_types``."""
        if prefs is None:
            return True
        enabled_types: Dict[str, bool] = prefs.enabled_types or {}
        # Default to True when the type key is absent (opt-out model)
        return enabled_types.get(notif_type.value, True)

    @staticmethod
    def _is_within_quiet_hours(prefs: Optional[NotificationPreference]) -> bool:
        """
        Return ``True`` when *right now* (in the user's stored timezone) falls
        inside their quiet-hour window.  Handles the midnight-wrap case
        (e.g. 22:00 → 07:00).

        Falls back to ``False`` (not quiet) when pytz is unavailable or the
        preference row has no quiet-hour window defined.
        """
        if prefs is None:
            return False

        start: Optional[time] = prefs.quiet_hours_start
        end: Optional[time] = prefs.quiet_hours_end
        if start is None or end is None:
            return False

        # Determine "now" in the user's timezone
        tz_name = prefs.timezone or "UTC"
        if pytz:
            try:
                tz = pytz.timezone(tz_name)
                now_local = datetime.now(tz).time()
            except pytz.exceptions.UnknownTimeZoneError:
                now_local = datetime.utcnow().time()
        else:  # pragma: no cover
            now_local = datetime.utcnow().time()

        # Normal window (e.g. 00:00 – 07:00)
        if start < end:
            return start <= now_local <= end

        # Midnight-wrapping window (e.g. 22:00 – 07:00)
        return now_local >= start or now_local <= end

    # ==================================================================
    # recipient contact-info resolution
    # ==================================================================

    def _resolve_contact_info(
        self,
        user_id: Optional[int],
        patient_id: Optional[int],
        channel: NotificationChannel,
        explicit_email: Optional[str],
        explicit_phone: Optional[str],
    ) -> Dict[str, Optional[str]]:
        """
        Return ``{"email": ..., "phone": ...}`` by first honouring any
        explicitly supplied values, then falling back to the user / patient
        row.  Contactless channels (IN_APP, PUSH) skip resolution entirely.
        """
        if channel in _CONTACTLESS_CHANNELS:
            return {"email": None, "phone": None}

        email = explicit_email
        phone = explicit_phone

        # Try user first, then patient
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
    # single notification
    # ==================================================================

    def send_notification(self, notification_in: NotificationCreate) -> Notification:
        """
        Persist a single notification, applying template rendering and
        preference gating.

        Flow
        ----
        1. Validate that at least one recipient identifier is present.
        2. If ``template_id`` is supplied, resolve & render it.
        3. Resolve contact info (email / phone) from the recipient entity.
        4. Gate against the recipient's preferences:
           - channel enabled?
           - notification type enabled?
           - currently inside quiet hours?
           If *any* gate blocks, the row is still created (audit trail) but
           its status is set to ``PENDING`` and ``error_message`` records the
           reason.  A scheduled notification that is blocked will be retried
           when the quiet-hour window closes by the background worker.
        5. Persist and return.
        """
        # --- 1. target validation -----------------------------------------
        if not notification_in.user_id and not notification_in.patient_id:
            raise ValueError("At least one of user_id or patient_id must be provided")

        # --- 2. template rendering ----------------------------------------
        subject = notification_in.subject
        message = notification_in.message

        if notification_in.template_id:
            rendered = self._resolve_template(
                notification_in.template_id,
                notification_in.template_variables,
            )
            subject = rendered["subject"] or subject
            message = rendered["message"]

        # --- 3. contact info ----------------------------------------------
        contact = self._resolve_contact_info(
            user_id=notification_in.user_id,
            patient_id=notification_in.patient_id,
            channel=notification_in.channel,
            explicit_email=notification_in.recipient_email,
            explicit_phone=notification_in.recipient_phone,
        )

        # --- 4. preference gate -------------------------------------------
        prefs = self._get_preferences(notification_in.user_id, notification_in.patient_id)
        blocked_reason: Optional[str] = None

        if not self._is_channel_enabled(prefs, notification_in.channel):
            blocked_reason = f"Channel '{notification_in.channel.value}' is disabled in recipient preferences"
        elif not self._is_type_enabled(prefs, notification_in.type):
            blocked_reason = f"Notification type '{notification_in.type.value}' is disabled in recipient preferences"
        elif self._is_within_quiet_hours(prefs):
            blocked_reason = "Recipient is within quiet hours"

        # Determine initial status
        if blocked_reason:
            initial_status = NotificationStatus.PENDING
            logger.info("Notification blocked for user_id=%s patient_id=%s: %s",
                        notification_in.user_id, notification_in.patient_id, blocked_reason)
        else:
            initial_status = (
                NotificationStatus.PENDING
                if notification_in.scheduled_for and notification_in.scheduled_for > datetime.utcnow()
                else NotificationStatus.SENT
            )

        # --- 5. persist ---------------------------------------------------
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
            sent_at=datetime.utcnow() if initial_status == NotificationStatus.SENT else None,
            error_message=blocked_reason,
            metadata=notification_in.metadata or {},
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    # ==================================================================
    # bulk notifications
    # ==================================================================

    def send_bulk_notifications(self, bulk_in: BulkNotificationCreate) -> int:
        """
        Resolve recipients from ``recipient_filters``, render the shared
        template once, then persist one ``Notification`` row per recipient
        through the same gating logic as single send.

        Supported filter keys
        ---------------------
        ``patient_ids``   – explicit list of patient IDs.
        ``lead_status``   – string value of a ``LeadStatus``; all matching
                            ``AILead`` rows become recipients (patient_id if
                            already converted, otherwise the lead's phone is
                            used as the target).

        Any unrecognised keys are logged and ignored.

        Returns the number of notification rows actually persisted.
        """
        # --- template pre-validation ---------------------------------------
        template = self.template_repo.get_by_code(bulk_in.template_id)
        if not template:
            raise ValueError(f"Template '{bulk_in.template_id}' not found")
        if not template.is_active:
            raise ValueError(f"Template '{bulk_in.template_id}' is not active")

        # --- recipient resolution ------------------------------------------
        recipients = self._resolve_bulk_recipients(bulk_in.recipient_filters)
        if not recipients:
            raise ValueError("No recipients matched the provided filters")

        # --- dispatch ------------------------------------------------------
        count = 0
        for recipient in recipients:
            notif_in = NotificationCreate(
                type=bulk_in.type,
                channel=bulk_in.channel,
                message="",                          # overridden by template
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
        """
        Turn ``recipient_filters`` into a list of dicts, each containing the
        keys needed by ``NotificationCreate``: ``patient_id``, ``user_id``,
        ``email``, ``phone``, ``template_variables``.
        """
        recipients: List[Dict[str, Any]] = []
        handled_keys = {"patient_ids", "lead_status"}

        # ── explicit patient ID list ──────────────────────────────────────
        if "patient_ids" in filters:
            patient_ids: List[int] = filters["patient_ids"]
            patients = (
                self.db.query(Patient)
                .filter(Patient.id.in_(patient_ids), Patient.tenant_id == self.tenant_id)
                .all()
            )
            for p in patients:
                recipients.append({
                    "patient_id": p.id,
                    "user_id": None,
                    "email": p.email,
                    "phone": p.phone,
                    "template_variables": {"patient_name": p.name},
                })

        # ── lead-status filter ────────────────────────────────────────────
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
                .filter(AILead.status == target_status, AILead.tenant_id == self.tenant_id)
                .all()
            )
            for lead in leads:
                recipients.append({
                    "patient_id": lead.patient_id,   # None if not yet converted
                    "user_id": None,
                    "email": lead.email,
                    "phone": lead.phone,
                    "template_variables": {"patient_name": lead.name},
                })

        # ── warn about unrecognised keys ──────────────────────────────────
        unknown_keys = set(filters.keys()) - handled_keys
        if unknown_keys:
            logger.warning(
                "Unrecognised recipient_filters keys ignored: %s", unknown_keys
            )

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
        """
        Paginated notification listing.

        ``filters`` may contain ``type`` (NotificationType) and/or
        ``status`` (NotificationStatus).
        """
        filters = filters or {}

        query = self.db.query(Notification).filter(Notification.tenant_id == self.tenant_id)

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
        """Current user's personal notification inbox."""
        return self.notification_repo.get_by_user(
            user_id, limit=limit, unread_only=unread_only
        )

    # ==================================================================
    # read-status mutations
    # ==================================================================

    def mark_as_read(self, notification_id: int) -> bool:
        """
        Mark a single notification as read.  Returns ``False`` when the
        notification does not exist (router maps → 404).
        """
        success = self.notification_repo.mark_as_read(notification_id)
        if success:
            self.db.commit()
        return success

    def mark_all_as_read(self, user_id: int) -> int:
        """Mark every unread notification for *user_id* as read; return count."""
        count = self.notification_repo.mark_all_as_read(user_id)
        self.db.commit()
        return count

    # ==================================================================
    # templates
    # ==================================================================

    def create_template(self, template_in: NotificationTemplateCreate) -> NotificationTemplate:
        """
        Create a new notification template.

        Duplicate ``code`` within the tenant is rejected so that template
        lookups by code remain unambiguous.
        """
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

    def get_templates(self, filters: Optional[Dict[str, Any]] = None) -> List[NotificationTemplate]:
        """
        List templates.  When ``filters["is_active"]`` is ``True`` (the
        default from the router) only active templates are returned.
        """
        filters = filters or {}

        if filters.get("is_active", True):
            return self.template_repo.get_active_templates()

        # is_active=False requested → return everything (admin view)
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.tenant_id == self.tenant_id
        )
        return query.all()

    # ==================================================================
    # preferences  (upsert pattern)
    # ==================================================================

    def get_user_preferences(self, user_id: int) -> NotificationPreferenceSchema:
        """
        Fetch preferences for *user_id*.  If no row exists yet the schema
        defaults are returned — the row is **not** created here; it will be
        created on the first explicit update (lazy-creation).
        """
        prefs = self.preference_repo.get_by_user(user_id)
        if prefs is None:
            # Return schema defaults without touching the DB
            return NotificationPreferenceSchema()
        return NotificationPreferenceSchema.model_validate(prefs)

    def update_user_preferences(
        self, user_id: int, prefs_in: NotificationPreferenceUpdate
    ) -> NotificationPreferenceSchema:
        """
        Partial-update (or create) the preference row for *user_id*.

        Only fields that were explicitly set by the caller are applied;
        everything else keeps its current value (or the schema default when
        the row is being created for the first time).
        """
        prefs = self.preference_repo.get_by_user(user_id)
        update_data = prefs_in.model_dump(exclude_unset=True)

        if prefs is None:
            # First write → create the row with defaults + caller overrides
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