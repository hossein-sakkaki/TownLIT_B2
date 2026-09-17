# apps/notifications/tasks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2025-10-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from utils.email.email_tools import send_custom_email
from utils.email.notification_respect_lines import pick_respect_line
from utils.email.signatures import pick_signature


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_email_notification(
    self,
    email,
    subject,
    message,
    link=None,
):
    """Send a notification email."""
    base_url = (
        getattr(settings, "FRONTEND_BASE_URL", "")
        or getattr(settings, "SITE_BASE_URL", "")
    )

    absolute_link = None

    if link:
        if link.startswith(("http://", "https://")):
            absolute_link = link
        elif base_url:
            absolute_link = (
                base_url.rstrip("/")
                + "/"
                + link.lstrip("/")
            )
        else:
            absolute_link = link

    context = {
        "email": email,
        "username": email.split("@")[0],
        "message": message,
        "link": absolute_link,
        "current_year": timezone.now().year,
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        "signature": pick_signature(),
        "respect_line": pick_respect_line(),
    }

    try:
        success = send_custom_email(
            to=email,
            subject=subject,
            template_path="emails/notifications/generic_notification.html",
            context=context,
            text_template_path=None,
        )

        if not success:
            raise RuntimeError(
                "send_custom_email returned False"
            )

        return True

    except Exception as error:
        logger.exception(
            "[Notif][Email] Delivery failed email=%s",
            email,
        )

        raise self.retry(
            exc=error,
            countdown=10,
        )


@shared_task
def publish_notification_campaign(
    campaign_id: int,
):
    """Prepare and publish a campaign."""
    from apps.notifications.campaigns.publisher import (
        prepare_and_dispatch_campaign,
    )

    prepare_and_dispatch_campaign(
        campaign_id
    )


@shared_task
def deliver_notification_campaign_batch(
    campaign_id: int,
    delivery_ids: list[int],
):
    """Deliver one campaign batch."""
    from apps.notifications.campaigns.publisher import (
        deliver_campaign_batch,
    )

    deliver_campaign_batch(
        campaign_id,
        delivery_ids,
    )


@shared_task
def dispatch_due_notification_campaigns():
    """Queue scheduled campaigns that are now due."""
    from apps.notifications.campaigns.publisher import (
        queue_due_campaign,
    )
    from apps.notifications.models import NotificationCampaign

    campaign_ids = list(
        NotificationCampaign.objects.filter(
            status=NotificationCampaign.Status.SCHEDULED,
            scheduled_at__lte=timezone.now(),
        ).values_list(
            "id",
            flat=True,
        )[:500]
    )

    for campaign_id in campaign_ids:
        queue_due_campaign(
            campaign_id
        )

    return len(campaign_ids)