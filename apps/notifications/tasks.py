# apps/notifications/tasks.py
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from utils.email.signatures import pick_signature
from utils.email.notification_respect_lines import pick_respect_line
import logging

from utils.email.email_tools import send_custom_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_email_notification(self, email, subject, message, link=None):
    """Send notification email via Celery + HTML template"""

    # Build absolute link for email (if only a path is provided)
    base_url = getattr(settings, "FRONTEND_BASE_URL", "") or getattr(settings, "SITE_BASE_URL", "")
    absolute_link = None
    if link:
        if link.startswith("http://") or link.startswith("https://"):
            absolute_link = link
        elif base_url:
            absolute_link = base_url.rstrip("/") + "/" + link.lstrip("/")
        else:
            # fallback: leave as-is
            absolute_link = link

    # Minimal context for the template 
    context = {
        "email": email,
        "username": email.split("@")[0],  # you can replace with real username later
        "message": message,
        "link": absolute_link,
        "current_year": timezone.now().year,
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        "signature": pick_signature(),
        "respect_line": pick_respect_line(),
    }

    
    try:
        # Single generic template for all notifications (can later branch by notif_type)
        success = send_custom_email(
            to=email,
            subject=subject,
            template_path="emails/notifications/generic_notification.html",
            context=context,
            text_template_path=None
        )

        if not success:
            logger.warning("❌ Notification email not sent to %s (send_custom_email returned False)", email)
            raise Exception("send_custom_email returned False")

        logger.info("✅ Notification email sent to %s", email)
        return True

    except Exception as e:
        logger.error("❌ Failed to send notification email to %s: %s", email, e, exc_info=True)
        # Retry via Celery
        raise self.retry(exc=e, countdown=10)
