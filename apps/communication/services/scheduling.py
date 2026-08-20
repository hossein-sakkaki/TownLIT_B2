# apps/communication/services/scheduling.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from dataclasses import dataclass
from datetime import datetime
import logging
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import current_app
from django.db.models import F
from django.utils import timezone

from apps.communication.constants import CampaignStatus
from apps.communication.models import EmailCampaign, ScheduledEmail

from .exceptions import CampaignStateError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CampaignQueueResult:
    campaign_id: int
    queued: bool
    task_id: str = ""
    status: str = ""
    error: str = ""


class CampaignSchedulingService:
    """
    Manage campaign scheduling and Celery dispatch.
    """

    schedulable_statuses = {
        CampaignStatus.DRAFT,
        CampaignStatus.READY,
        CampaignStatus.PAUSED,
        CampaignStatus.FAILED,
        CampaignStatus.SCHEDULED,
    }

    queueable_statuses = {
        CampaignStatus.DRAFT,
        CampaignStatus.READY,
        CampaignStatus.PAUSED,
        CampaignStatus.FAILED,
    }

    terminal_statuses = {
        CampaignStatus.SENT,
        CampaignStatus.CANCELED,
    }

    def schedule(
        self,
        *,
        campaign_id,
        run_at,
        timezone_name="UTC",
    ):
        """
        Schedule a campaign for future delivery.
        """

        run_at = self._normalize_run_at(
            run_at,
            timezone_name,
        )

        if run_at <= timezone.now():
            raise CampaignStateError(
                "Scheduled time must be in the future."
            )

        updated = EmailCampaign.objects.filter(
            pk=campaign_id,
            status__in=self.schedulable_statuses,
        ).update(
            status=CampaignStatus.SCHEDULED,
            scheduled_time=run_at,
            schedule_timezone=timezone_name,
            queued_at=None,
            celery_task_id="",
            failed_at=None,
            completed_at=None,
            last_error="",
        )

        if not updated:
            raise CampaignStateError(
                "Campaign cannot be scheduled from its current state."
            )

        return EmailCampaign.objects.get(
            pk=campaign_id
        )

    def unschedule(self, *, campaign_id):
        """
        Return a scheduled campaign to draft.
        """

        updated = EmailCampaign.objects.filter(
            pk=campaign_id,
            status=CampaignStatus.SCHEDULED,
        ).update(
            status=CampaignStatus.DRAFT,
            scheduled_time=None,
            queued_at=None,
            celery_task_id="",
            last_error="",
        )

        if not updated:
            raise CampaignStateError(
                "Only scheduled campaigns can be unscheduled."
            )

        return EmailCampaign.objects.get(
            pk=campaign_id
        )

    def queue_now(self, *, campaign_id):
        """
        Queue an eligible campaign for immediate delivery.
        """

        task_id = str(uuid.uuid4())
        now = timezone.now()

        updated = EmailCampaign.objects.filter(
            pk=campaign_id,
            status__in=self.queueable_statuses,
        ).update(
            status=CampaignStatus.QUEUED,
            queued_at=now,
            last_dispatch_at=now,
            celery_task_id=task_id,
            dispatch_attempt_count=F("dispatch_attempt_count") + 1,
            failed_at=None,
            completed_at=None,
            last_error="",
        )

        if not updated:
            campaign = EmailCampaign.objects.filter(
                pk=campaign_id
            ).only(
                "status"
            ).first()

            return CampaignQueueResult(
                campaign_id=campaign_id,
                queued=False,
                status=campaign.status if campaign else "missing",
                error=(
                    "Campaign is not eligible for immediate delivery."
                ),
            )

        return self._enqueue(
            campaign_id=campaign_id,
            task_id=task_id,
        )

    def dispatch_due(self, *, limit=100):
        """
        Claim and queue due scheduled campaigns.
        """

        now = timezone.now()

        campaign_ids = list(
            EmailCampaign.objects.filter(
                status=CampaignStatus.SCHEDULED,
                scheduled_time__lte=now,
            ).order_by(
                "scheduled_time",
                "id",
            ).values_list(
                "id",
                flat=True,
            )[:limit]
        )

        results = []

        for campaign_id in campaign_ids:
            result = self._claim_due_campaign(
                campaign_id=campaign_id,
                now=now,
            )

            if result:
                results.append(result)

        return results

    def cancel_queued(self, *, campaign_id):
        """
        Cancel a campaign that has not started sending.
        """

        campaign = EmailCampaign.objects.filter(
            pk=campaign_id,
            status=CampaignStatus.QUEUED,
        ).only(
            "id",
            "celery_task_id",
        ).first()

        if not campaign:
            raise CampaignStateError(
                "Only queued campaigns can be canceled."
            )

        updated = EmailCampaign.objects.filter(
            pk=campaign_id,
            status=CampaignStatus.QUEUED,
            celery_task_id=campaign.celery_task_id,
        ).update(
            status=CampaignStatus.CANCELED,
            canceled_at=timezone.now(),
            completed_at=timezone.now(),
            last_error="",
        )

        if not updated:
            raise CampaignStateError(
                "Campaign started before it could be canceled."
            )

        if campaign.celery_task_id:
            current_app.control.revoke(
                campaign.celery_task_id,
                terminate=False,
            )

        return EmailCampaign.objects.get(
            pk=campaign_id
        )

    def sync_legacy_due_schedules(self, *, limit=100):
        """
        Bridge old ScheduledEmail records into the new scheduler.
        """

        now = timezone.now()

        schedules = ScheduledEmail.objects.filter(
            is_sent=False,
            run_at__lte=now,
        ).select_related(
            "campaign"
        ).order_by(
            "run_at",
            "id",
        )[:limit]

        synced = 0

        for schedule in schedules:
            campaign = schedule.campaign

            if campaign.status in self.terminal_statuses:
                schedule.is_sent = True
                schedule.executed_at = now
                schedule.save(
                    update_fields=[
                        "is_sent",
                        "executed_at",
                    ]
                )
                continue

            if campaign.status in {
                CampaignStatus.QUEUED,
                CampaignStatus.SENDING,
            }:
                continue

            updated = EmailCampaign.objects.filter(
                pk=campaign.pk,
                status__in=self.schedulable_statuses,
            ).update(
                status=CampaignStatus.SCHEDULED,
                scheduled_time=schedule.run_at,
                schedule_timezone="UTC",
                last_error="",
            )

            if updated:
                synced += 1

        return synced

    def mark_legacy_execution(self, *, campaign_id):
        """
        Mark due legacy schedule rows as executed.
        """

        return ScheduledEmail.objects.filter(
            campaign_id=campaign_id,
            is_sent=False,
            run_at__lte=timezone.now(),
        ).update(
            is_sent=True,
            executed_at=timezone.now(),
        )

    def _claim_due_campaign(self, *, campaign_id, now):
        task_id = str(uuid.uuid4())

        updated = EmailCampaign.objects.filter(
            pk=campaign_id,
            status=CampaignStatus.SCHEDULED,
            scheduled_time__lte=now,
        ).update(
            status=CampaignStatus.QUEUED,
            queued_at=now,
            last_dispatch_at=now,
            celery_task_id=task_id,
            dispatch_attempt_count=F("dispatch_attempt_count") + 1,
            last_error="",
        )

        if not updated:
            return None

        return self._enqueue(
            campaign_id=campaign_id,
            task_id=task_id,
        )

    def _enqueue(self, *, campaign_id, task_id):
        try:
            from apps.communication.tasks.campaigns import (
                send_campaign_task,
            )

            send_campaign_task.apply_async(
                args=[campaign_id],
                task_id=task_id,
            )

            return CampaignQueueResult(
                campaign_id=campaign_id,
                queued=True,
                task_id=task_id,
                status=CampaignStatus.QUEUED,
            )

        except Exception as error:
            logger.exception(
                "Unable to queue campaign campaign=%s task=%s",
                campaign_id,
                task_id,
            )

            EmailCampaign.objects.filter(
                pk=campaign_id,
                status=CampaignStatus.QUEUED,
                celery_task_id=task_id,
            ).update(
                status=CampaignStatus.SCHEDULED,
                queued_at=None,
                celery_task_id="",
                last_error=str(error)[:4000],
            )

            return CampaignQueueResult(
                campaign_id=campaign_id,
                queued=False,
                task_id=task_id,
                status=CampaignStatus.SCHEDULED,
                error=str(error),
            )

    def _normalize_run_at(
        self,
        run_at,
        timezone_name,
    ):
        if not isinstance(run_at, datetime):
            raise CampaignStateError(
                "Scheduled time must be a datetime value."
            )

        try:
            tz = ZoneInfo(
                timezone_name or "UTC"
            )
        except ZoneInfoNotFoundError as error:
            raise CampaignStateError(
                f"Unknown scheduling time zone: {timezone_name}"
            ) from error

        if timezone.is_naive(run_at):
            run_at = timezone.make_aware(
                run_at,
                timezone=tz,
            )

        return run_at