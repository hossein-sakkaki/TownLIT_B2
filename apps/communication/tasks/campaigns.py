# apps/communication/tasks/campaigns.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from dataclasses import asdict
from datetime import timedelta
import logging

from celery import shared_task
from django.utils import timezone

from apps.communication.constants import CampaignStatus
from apps.communication.models import EmailCampaign
from apps.communication.services import (
    CampaignDeliveryService,
    CampaignSchedulingService,
)


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.communication.tasks.send_campaign",
    acks_late=True,
)
def send_campaign_task(self, campaign_id):
    """
    Deliver one queued campaign.
    """

    task_id = self.request.id or ""

    delivery_service = CampaignDeliveryService()
    scheduling_service = CampaignSchedulingService()

    try:
        result = delivery_service.send(
            campaign_id,
            task_id=task_id,
        )

        if result.status in {
            CampaignStatus.SENT,
            CampaignStatus.FAILED,
            CampaignStatus.CANCELED,
        }:
            scheduling_service.mark_legacy_execution(
                campaign_id=campaign_id
            )

        return asdict(result)

    except Exception as error:
        logger.exception(
            "Campaign worker failed campaign=%s task=%s",
            campaign_id,
            task_id,
        )

        delivery_service.mark_worker_failure(
            campaign_id=campaign_id,
            task_id=task_id,
            error=error,
        )

        scheduling_service.mark_legacy_execution(
            campaign_id=campaign_id
        )

        raise


@shared_task(
    name="apps.communication.tasks.dispatch_due_campaigns",
)
def dispatch_due_campaigns():
    """
    Queue campaigns whose scheduled time has arrived.
    """

    service = CampaignSchedulingService()

    legacy_synced = service.sync_legacy_due_schedules()

    results = service.dispatch_due(
        limit=100
    )

    queued = sum(
        1
        for result in results
        if result.queued
    )

    failed = len(results) - queued

    logger.info(
        "Campaign dispatcher completed legacy_synced=%s "
        "queued=%s failed=%s",
        legacy_synced,
        queued,
        failed,
    )

    return {
        "legacy_synced": legacy_synced,
        "queued": queued,
        "failed": failed,
    }


@shared_task(
    name="apps.communication.tasks.run_scheduled_emails",
)
def run_scheduled_emails():
    """
    Keep the old periodic task name working.
    """

    return dispatch_due_campaigns.run()


@shared_task(
    name="apps.communication.tasks.recover_stale_campaigns",
)
def recover_stale_campaigns():
    """
    Recover campaigns left queued without worker execution.
    """

    stale_before = timezone.now() - timedelta(
        minutes=30
    )

    recovered = EmailCampaign.objects.filter(
        status=CampaignStatus.QUEUED,
        queued_at__lt=stale_before,
    ).update(
        status=CampaignStatus.SCHEDULED,
        queued_at=None,
        celery_task_id="",
        last_error="Recovered from a stale queued state.",
    )

    if recovered:
        logger.warning(
            "Recovered %s stale queued campaign(s).",
            recovered,
        )

    return recovered