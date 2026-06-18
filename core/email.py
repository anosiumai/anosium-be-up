"""
Email Service
=============

Centralised email sending for the platform, built on `fastapi-mail`.

Responsibilities
----------------
* Password reset emails
* Email verification emails
* Welcome emails (new user / new clinic admin)
* Appointment reminder emails
* Generic notification emails (used by NotificationService for the EMAIL channel)

Design notes
------------
1. **Email is an optional feature.** ``core.config.is_feature_enabled("email")``
   returns ``False`` when ``SMTP_HOST`` is not set. Every ``send_*`` method on
   this service checks ``is_configured`` first and, if email isn't configured,
   logs a warning and returns ``False`` instead of raising. This means a dev
   environment with no SMTP credentials never crashes a request just because
   it tried to send an email.

2. **All sending is async.** `fastapi-mail`'s `FastMail.send_message()` is a
   coroutine (it uses `aiosmtplib`). Service-layer code that is synchronous
   (most of `services/*.py`) should NOT call this service directly — use the
   Celery task wrappers in `worker/email_tasks.py` via
   `core.email.dispatch_email(...)`, which handles both the "Celery is
   configured" and "Celery is not configured, send inline" cases.

3. **Templates** live in `core/email_templates/*.html` and are rendered via
   `fastapi-mail`'s built-in Jinja2 integration (`TEMPLATE_FOLDER` +
   `template_body=` + `template_name=`).

4. **Never let an email failure break a business transaction.** Password
   reset token creation, user registration, etc. must succeed even if the
   SMTP server is down — the token/record is the source of truth, the email
   is a best-effort notification. Every method here catches exceptions
   internally and returns ``bool``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# fastapi-mail is an optional dependency. If it isn't installed (e.g. a
# minimal CI image that never sends email), importing this module should not
# crash the whole application — it should just make `is_configured` False.
# ---------------------------------------------------------------------------
try:
    from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

    _FASTMAIL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when dependency missing
    ConnectionConfig = None  # type: ignore[assignment]
    FastMail = None  # type: ignore[assignment]
    MessageSchema = None  # type: ignore[assignment]
    MessageType = None  # type: ignore[assignment]
    _FASTMAIL_AVAILABLE = False
    logger.warning(
        "fastapi-mail is not installed. Email sending is disabled. "
        "Install with: pip install fastapi-mail"
    )


TEMPLATE_FOLDER = Path(__file__).resolve().parent / "email_templates"


class EmailService:
    """
    Thin wrapper around `fastapi-mail` with template helpers for every
    transactional email the platform sends.

    Usage
    -----
        from core.email import email_service

        await email_service.send_password_reset_email(
            to_email="doctor@clinic.com",
            user_name="Dr. Rao",
            reset_token="abc123",
        )

    For sync call sites, use `worker.email_tasks` instead (Celery wrappers).
    """

    def __init__(self) -> None:
        self._fastmail: Optional["FastMail"] = None

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        """
        True when fastapi-mail is installed AND the minimum SMTP settings
        (host + from-address) are present.

        This mirrors `core.config.is_feature_enabled("email")` but is kept
        local so this module has no import-order dependency surprises.
        """
        return bool(
            _FASTMAIL_AVAILABLE
            and settings.SMTP_HOST
            and settings.SMTP_FROM_EMAIL
        )

    def _get_fastmail(self) -> "FastMail":
        """
        Lazily build and cache the `FastMail` client.

        Raises:
            RuntimeError: if called when `is_configured` is False. Callers in
            this module always check `is_configured` first, so this should
            never be hit in practice — it's a defensive guard.
        """
        if not self.is_configured:
            raise RuntimeError(
                "EmailService is not configured (SMTP_HOST/SMTP_FROM_EMAIL "
                "missing or fastapi-mail not installed)"
            )

        if self._fastmail is None:
            conf = ConnectionConfig(
                MAIL_USERNAME=settings.SMTP_USER or "",
                MAIL_PASSWORD=settings.SMTP_PASSWORD or "",
                MAIL_FROM=settings.SMTP_FROM_EMAIL,
                MAIL_FROM_NAME=settings.SMTP_FROM_NAME or settings.APP_NAME,
                MAIL_PORT=settings.SMTP_PORT or 587,
                MAIL_SERVER=settings.SMTP_HOST,
                MAIL_STARTTLS=settings.SMTP_TLS,
                MAIL_SSL_TLS=not settings.SMTP_TLS,
                USE_CREDENTIALS=bool(settings.SMTP_USER),
                VALIDATE_CERTS=True,
                TEMPLATE_FOLDER=TEMPLATE_FOLDER,
            )
            self._fastmail = FastMail(conf)

        return self._fastmail

    # ------------------------------------------------------------------
    # low-level send
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to: List[str] | str,
        subject: str,
        template_name: str,
        template_body: Dict[str, Any],
    ) -> bool:
        """
        Render *template_name* with *template_body* and send to *to*.

        Returns ``True`` on success, ``False`` on any failure (including
        "email not configured"). Never raises — callers should treat email as
        best-effort.

        Args:
            to: single recipient address or list of addresses.
            subject: email subject line.
            template_name: filename under `core/email_templates/` (e.g.
                ``"password_reset.html"``).
            template_body: dict of variables passed to the Jinja2 template.
        """
        if not self.is_configured:
            logger.warning(
                "Email not sent (SMTP not configured): to=%s subject=%r template=%s",
                to,
                subject,
                template_name,
            )
            return False

        recipients = [to] if isinstance(to, str) else to

        try:
            message = MessageSchema(
                subject=subject,
                recipients=recipients,
                template_body=template_body,
                subtype=MessageType.html,
            )
            fm = self._get_fastmail()
            await fm.send_message(message, template_name=template_name)

            logger.info("Email sent: to=%s subject=%r template=%s", recipients, subject, template_name)
            return True

        except Exception:
            logger.exception(
                "Failed to send email: to=%s subject=%r template=%s",
                recipients,
                subject,
                template_name,
            )
            return False

    # ------------------------------------------------------------------
    # transactional emails
    # ------------------------------------------------------------------

    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_token: str,
    ) -> bool:
        """
        Send the "reset your password" email.

        The reset link points at ``{FRONTEND_URL}/reset-password?token=...``.
        The token itself is opaque to this method — it was already generated
        and persisted by `AuthService.create_password_reset_token`.
        """
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        return await self.send_email(
            to=to_email,
            subject=f"Reset your {settings.APP_NAME} password",
            template_name="password_reset.html",
            template_body={
                "app_name": settings.APP_NAME,
                "user_name": user_name,
                "reset_url": reset_url,
                "expires_in_hours": 24,
            },
        )

    async def send_email_verification_email(
        self,
        to_email: str,
        user_name: str,
        verification_token: str,
    ) -> bool:
        """
        Send the "verify your email address" email sent after registration.

        The verification link points at
        ``{FRONTEND_URL}/verify-email?token=...``.
        """
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

        return await self.send_email(
            to=to_email,
            subject=f"Verify your email for {settings.APP_NAME}",
            template_name="email_verification.html",
            template_body={
                "app_name": settings.APP_NAME,
                "user_name": user_name,
                "verify_url": verify_url,
                "expires_in_days": 7,
            },
        )

    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        tenant_name: Optional[str] = None,
        role: Optional[str] = None,
    ) -> bool:
        """
        Send the "welcome to the platform" email.

        Used both for:
          * a new clinic's admin user (right after tenant registration), and
          * staff/doctor accounts created by a clinic admin.

        ``tenant_name`` and ``role`` are optional so the same template works
        for both the super-admin-created super-admin case (neither set) and
        the clinic-staff case (both set).
        """
        login_url = f"{settings.FRONTEND_URL}/login"

        return await self.send_email(
            to=to_email,
            subject=f"Welcome to {settings.APP_NAME}",
            template_name="welcome.html",
            template_body={
                "app_name": settings.APP_NAME,
                "user_name": user_name,
                "tenant_name": tenant_name,
                "role": role,
                "login_url": login_url,
            },
        )

    async def send_appointment_reminder_email(
        self,
        to_email: str,
        patient_name: str,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        clinic_name: str,
        appointment_code: Optional[str] = None,
    ) -> bool:
        """
        Send an appointment reminder email.

        Date/time are passed as pre-formatted strings (rather than
        `date`/`time` objects) so this method has no dependency on how the
        caller formats things for the recipient's locale.
        """
        return await self.send_email(
            to=to_email,
            subject=f"Appointment Reminder — {clinic_name}",
            template_name="appointment_reminder.html",
            template_body={
                "app_name": settings.APP_NAME,
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "clinic_name": clinic_name,
                "appointment_code": appointment_code,
            },
        )

    async def send_generic_notification_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        recipient_name: Optional[str] = None,
    ) -> bool:
        """
        Send a plain notification email.

        This is the EMAIL-channel delivery path used by
        `NotificationService.send_notification` for notification types that
        don't have a dedicated template (payment receipts, follow-ups, system
        messages, etc.). ``message`` is inserted as-is into the template body
        — callers are responsible for any text formatting.
        """
        return await self.send_email(
            to=to_email,
            subject=subject,
            template_name="notification_generic.html",
            template_body={
                "app_name": settings.APP_NAME,
                "recipient_name": recipient_name,
                "subject": subject,
                "message": message,
            },
        )


# Module-level singleton — import this, don't instantiate EmailService yourself.
email_service = EmailService()


# ---------------------------------------------------------------------------
# dispatch helper — bridges sync service code to async email sending
# ---------------------------------------------------------------------------

def dispatch_email(task_name: str, /, **kwargs: Any) -> bool:
    """
    Fire-and-forget email dispatch from synchronous service code.

    Behaviour
    ---------
    * If Celery is configured (``settings.CELERY_BROKER_URL`` is set), the
      named task is enqueued via ``.delay()`` and this function returns
      immediately. Delivery happens asynchronously on a worker process —
      transient SMTP failures are retried there (see
      ``worker/email_tasks.py``).
    * If Celery is **not** configured (e.g. local dev without Redis), the
      corresponding `EmailService` coroutine is run inline via
      ``asyncio.run()``. This blocks the request for the duration of the SMTP
      call, which is acceptable for local development but should not happen
      in production — configure ``CELERY_BROKER_URL``.
    * Any error (including "email not configured") is logged and swallowed.
      This function always returns a ``bool`` and never raises, so it is safe
      to call from any service method without a surrounding try/except.

    Args:
        task_name: one of ``"password_reset"``, ``"email_verification"``,
            ``"welcome"``, ``"appointment_reminder"``, ``"generic_notification"``.
        **kwargs: forwarded to the corresponding `EmailService.send_*` method
            / Celery task.

    Returns:
        ``True`` if the email was sent (sync path) or successfully enqueued
        (Celery path); ``False`` otherwise.
    """
    import asyncio

    _TASK_TO_METHOD = {
        "password_reset": "send_password_reset_email",
        "email_verification": "send_email_verification_email",
        "welcome": "send_welcome_email",
        "appointment_reminder": "send_appointment_reminder_email",
        "generic_notification": "send_generic_notification_email",
    }

    if task_name not in _TASK_TO_METHOD:
        logger.error("dispatch_email: unknown task_name %r", task_name)
        return False

    if settings.CELERY_BROKER_URL:
        try:
            # Imported lazily so that environments without Celery installed
            # (and without CELERY_BROKER_URL set) never import celery at all.
            from worker.email_tasks import EMAIL_TASK_DISPATCH

            EMAIL_TASK_DISPATCH[task_name].delay(**kwargs)
            return True
        except Exception:
            logger.exception(
                "Failed to enqueue Celery email task %r — falling back to inline send",
                task_name,
            )
            # fall through to inline path

    # --- inline (sync) fallback -------------------------------------------
    method = getattr(email_service, _TASK_TO_METHOD[task_name])

    try:
        return asyncio.run(method(**kwargs))
    except RuntimeError as exc:
        # asyncio.run() cannot be called from a context that already has a
        # running event loop (e.g. inside an `async def` FastAPI route that
        # calls a sync service method directly). In that case, schedule the
        # coroutine on the existing loop instead.
        if "asyncio.run() cannot be called" in str(exc):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(method(**kwargs))
        logger.exception("dispatch_email inline send failed for task %r", task_name)
        return False
    except Exception:
        logger.exception("dispatch_email inline send failed for task %r", task_name)
        return False