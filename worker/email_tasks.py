"""
Celery tasks for email delivery.

Each task wraps one `EmailService.send_*` coroutine. Tasks:

* Run the coroutine via `asyncio.run()` (each Celery task execution gets its
  own thread/process under the default prefork pool, so there is no
  "event loop already running" conflict).
* Retry up to 3 times with a 60-second delay on any exception (transient SMTP
  errors, DNS hiccups, etc.).
* Log — but do not re-raise past the final retry — so a permanently-failing
  email (e.g. invalid recipient address) doesn't poison the queue forever.

`EMAIL_TASK_DISPATCH` maps the logical task names used by
`core.email.dispatch_email()` to these Celery tasks, so application code never
needs to import Celery task objects directly.
"""

import asyncio
import logging
from typing import Any, Dict

from worker.celery_app import celery_app
from core.email import email_service

logger = logging.getLogger(__name__)


def _run(coro) -> bool:
    """Execute an async EmailService coroutine from sync Celery task context."""
    return asyncio.run(coro)


@celery_app.task(
    name="email.send_password_reset",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_password_reset_email_task(self, to_email: str, user_name: str, reset_token: str) -> bool:
    """Send a password-reset email. Retries on transient failure."""
    try:
        sent = _run(
            email_service.send_password_reset_email(
                to_email=to_email, user_name=user_name, reset_token=reset_token
            )
        )
        if not sent:
            raise RuntimeError("send_password_reset_email returned False")
        return sent
    except Exception as exc:
        logger.warning("send_password_reset_email_task failed (attempt %s): %s", self.request.retries, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="email.send_email_verification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_email_verification_email_task(self, to_email: str, user_name: str, verification_token: str) -> bool:
    """Send an email-verification email. Retries on transient failure."""
    try:
        sent = _run(
            email_service.send_email_verification_email(
                to_email=to_email, user_name=user_name, verification_token=verification_token
            )
        )
        if not sent:
            raise RuntimeError("send_email_verification_email returned False")
        return sent
    except Exception as exc:
        logger.warning("send_email_verification_email_task failed (attempt %s): %s", self.request.retries, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="email.send_welcome",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_welcome_email_task(
    self,
    to_email: str,
    user_name: str,
    tenant_name: str | None = None,
    role: str | None = None,
) -> bool:
    """Send a welcome email to a newly created user. Retries on transient failure."""
    try:
        sent = _run(
            email_service.send_welcome_email(
                to_email=to_email, user_name=user_name, tenant_name=tenant_name, role=role
            )
        )
        if not sent:
            raise RuntimeError("send_welcome_email returned False")
        return sent
    except Exception as exc:
        logger.warning("send_welcome_email_task failed (attempt %s): %s", self.request.retries, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="email.send_appointment_reminder",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_appointment_reminder_email_task(
    self,
    to_email: str,
    patient_name: str,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    clinic_name: str,
    appointment_code: str | None = None,
) -> bool:
    """Send an appointment reminder email. Retries on transient failure."""
    try:
        sent = _run(
            email_service.send_appointment_reminder_email(
                to_email=to_email,
                patient_name=patient_name,
                doctor_name=doctor_name,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                clinic_name=clinic_name,
                appointment_code=appointment_code,
            )
        )
        if not sent:
            raise RuntimeError("send_appointment_reminder_email returned False")
        return sent
    except Exception as exc:
        logger.warning("send_appointment_reminder_email_task failed (attempt %s): %s", self.request.retries, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="email.send_generic_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_generic_notification_email_task(
    self,
    to_email: str,
    subject: str,
    message: str,
    recipient_name: str | None = None,
) -> bool:
    """Send a generic notification email (used by NotificationService). Retries on transient failure."""
    try:
        sent = _run(
            email_service.send_generic_notification_email(
                to_email=to_email, subject=subject, message=message, recipient_name=recipient_name
            )
        )
        if not sent:
            raise RuntimeError("send_generic_notification_email returned False")
        return sent
    except Exception as exc:
        logger.warning("send_generic_notification_email_task failed (attempt %s): %s", self.request.retries, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Dispatch table consumed by `core.email.dispatch_email()`
# ---------------------------------------------------------------------------
EMAIL_TASK_DISPATCH: Dict[str, Any] = {
    "password_reset": send_password_reset_email_task,
    "email_verification": send_email_verification_email_task,
    "welcome": send_welcome_email_task,
    "appointment_reminder": send_appointment_reminder_email_task,
    "generic_notification": send_generic_notification_email_task,
}