# apps/communication/services/campaign_delivery.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from dataclasses import dataclass
import logging

from django.db.models import Sum
from django.utils import timezone

from apps.communication.constants import (
    CampaignStatus,
    EmailDeliveryStatus,
    EmailEventType,
)
from apps.communication.models import EmailCampaign, EmailEvent, EmailLog
from utils.email.email_tools import send_custom_email

from .recipients import AudienceResolver, EmailRecipient
from .rendering import CampaignRenderer
from .suppression import EmailSuppressionService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CampaignSendResult:
    campaign_id: int
    targeted: int
    sent: int
    suppressed: int
    failed: int
    status: str
    error: str = ""


class CampaignDeliveryService:
    sendable_statuses = {
        CampaignStatus.DRAFT,
        CampaignStatus.READY,
        CampaignStatus.SCHEDULED,
        CampaignStatus.QUEUED,
        CampaignStatus.PAUSED,
        CampaignStatus.FAILED,
    }

    terminal_delivery_statuses = {
        EmailDeliveryStatus.SENT,
        EmailDeliveryStatus.DELIVERED,
        EmailDeliveryStatus.BOUNCED,
        EmailDeliveryStatus.COMPLAINED,
    }

    def __init__(self):
        self.audience_resolver = AudienceResolver()
        self.suppression_service = EmailSuppressionService()
        self.renderer = CampaignRenderer()

    def send(self, campaign_id, *, task_id=None):
        campaign = self._claim_campaign(
            campaign_id,
            task_id=task_id,
        )

        if not campaign:
            return self._unavailable_result(campaign_id)

        try:
            recipients = self.audience_resolver.resolve_campaign(campaign)
        except Exception as error:
            return self._fail_campaign(campaign, str(error))

        if not recipients:
            return self._fail_campaign(
                campaign,
                "Campaign has no recipients.",
            )

        suppressed = 0

        for recipient in recipients:
            if self._already_delivered(campaign, recipient):
                continue

            reason = self.suppression_service.get_reason(
                campaign,
                recipient,
            )

            if reason:
                self._record_suppressed(
                    campaign,
                    recipient,
                    reason,
                )
                suppressed += 1
                continue

            self._send_recipient(
                campaign,
                recipient,
            )

        totals = self._refresh_totals(campaign)

        if totals["sent_count"] == 0:
            error = (
                "All targeted recipients were suppressed."
                if suppressed >= len(recipients) and totals["failed_count"] == 0
                else "No campaign emails were sent successfully."
            )

            return self._fail_campaign(
                campaign,
                error,
                refresh_totals=False,
            )

        completed_at = timezone.now()

        EmailCampaign.objects.filter(
            pk=campaign.pk,
            status=CampaignStatus.SENDING,
        ).update(
            status=CampaignStatus.SENT,
            sent_at=completed_at,
            completed_at=completed_at,
            failed_at=None,
            last_error="",
        )

        return CampaignSendResult(
            campaign_id=campaign.id,
            targeted=len(recipients),
            sent=totals["sent_count"],
            suppressed=suppressed,
            failed=totals["failed_count"],
            status=CampaignStatus.SENT,
        )

    def send_test(self, campaign):
        if not campaign.test_email:
            return False

        recipient = EmailRecipient(
            email=campaign.test_email,
            first_name="Friend",
            username="test_user",
            source="test",
        )

        rendered = self.renderer.render(
            campaign=campaign,
            recipient=recipient,
            preview=True,
        )

        return send_custom_email(
            to=recipient.email,
            subject=rendered.subject,
            template_path=rendered.template_path,
            context=rendered.context,
        )

    def mark_worker_failure(self, *, campaign_id, task_id, error):
        EmailCampaign.objects.filter(
            pk=campaign_id,
            status=CampaignStatus.SENDING,
            celery_task_id=task_id,
        ).update(
            status=CampaignStatus.FAILED,
            failed_at=timezone.now(),
            completed_at=timezone.now(),
            last_error=str(error)[:4000],
        )

    def _claim_campaign(self, campaign_id, *, task_id=None):
        filters = {
            "pk": campaign_id,
            "status__in": self.sendable_statuses,
        }

        if task_id:
            filters["celery_task_id"] = task_id

        updated = EmailCampaign.objects.filter(**filters).update(
            status=CampaignStatus.SENDING,
            started_at=timezone.now(),
            completed_at=None,
            failed_at=None,
            last_error="",
        )

        if updated:
            return self._get_campaign(campaign_id)

        if task_id and EmailCampaign.objects.filter(
            pk=campaign_id,
            status=CampaignStatus.SENDING,
            celery_task_id=task_id,
        ).exists():
            return self._get_campaign(campaign_id)

        return None

    def _get_campaign(self, campaign_id):
        return EmailCampaign.objects.select_related(
            "template",
            "template__theme",
            "theme",
            "topic",
            "audience",
        ).get(pk=campaign_id)

    def _already_delivered(self, campaign, recipient):
        return EmailLog.objects.filter(
            campaign=campaign,
            email__iexact=recipient.email,
            status__in=self.terminal_delivery_statuses,
        ).exists()

    def _send_recipient(self, campaign, recipient):
        delivery = self._prepare_delivery(
            campaign,
            recipient,
        )

        try:
            rendered = self.renderer.render(
                campaign=campaign,
                recipient=recipient,
                delivery=delivery,
            )

            success = send_custom_email(
                to=recipient.email,
                subject=rendered.subject,
                template_path=rendered.template_path,
                context=rendered.context,
            )

            if success:
                self._mark_sent(delivery)
                return True

            self._mark_failed(
                delivery,
                "Email sender returned False.",
            )
            return False

        except Exception as error:
            logger.exception(
                "Campaign email failed campaign=%s email=%s",
                campaign.id,
                recipient.email,
            )

            self._mark_failed(
                delivery,
                str(error),
            )
            return False

    def _prepare_delivery(self, campaign, recipient):
        delivery = EmailLog.objects.filter(
            campaign=campaign,
            email__iexact=recipient.email,
        ).order_by("-id").first()

        now = timezone.now()

        if not delivery:
            return EmailLog.objects.create(
                campaign=campaign,
                user_id=recipient.user_id,
                external_contact_id=recipient.external_contact_id,
                email=recipient.email,
                status=EmailDeliveryStatus.SENDING,
                queued_at=now,
                sent_at=None,
                metadata={
                    "recipient_source": recipient.source,
                },
            )

        delivery.user_id = recipient.user_id
        delivery.external_contact_id = recipient.external_contact_id
        delivery.status = EmailDeliveryStatus.SENDING
        delivery.queued_at = delivery.queued_at or now
        delivery.sent_at = None
        delivery.failed_at = None
        delivery.failure_code = ""
        delivery.failure_message = ""
        delivery.metadata = {
            **(delivery.metadata or {}),
            "recipient_source": recipient.source,
        }
        delivery.save()

        return delivery

    def _mark_sent(self, delivery):
        now = timezone.now()

        delivery.status = EmailDeliveryStatus.SENT
        delivery.sent_at = now
        delivery.failed_at = None
        delivery.failure_code = ""
        delivery.failure_message = ""
        delivery.last_event_at = now
        delivery.save(update_fields=[
            "status",
            "sent_at",
            "failed_at",
            "failure_code",
            "failure_message",
            "last_event_at",
        ])

        EmailEvent.objects.create(
            delivery=delivery,
            event_type=EmailEventType.SENT,
            occurred_at=now,
        )

    def _record_suppressed(self, campaign, recipient, reason):
        delivery = EmailLog.objects.filter(
            campaign=campaign,
            email__iexact=recipient.email,
        ).order_by("-id").first()

        if delivery:
            delivery.user_id = recipient.user_id
            delivery.external_contact_id = recipient.external_contact_id
            delivery.status = EmailDeliveryStatus.SUPPRESSED
            delivery.sent_at = None
            delivery.failure_code = reason
            delivery.failure_message = (
                "Recipient suppressed by email preferences."
            )
            delivery.metadata = {
                **(delivery.metadata or {}),
                "recipient_source": recipient.source,
            }
            delivery.save()
            return

        EmailLog.objects.create(
            campaign=campaign,
            user_id=recipient.user_id,
            external_contact_id=recipient.external_contact_id,
            email=recipient.email,
            status=EmailDeliveryStatus.SUPPRESSED,
            sent_at=None,
            failure_code=reason,
            failure_message="Recipient suppressed by email preferences.",
            metadata={
                "recipient_source": recipient.source,
            },
        )

    def _mark_failed(self, delivery, message):
        now = timezone.now()

        delivery.status = EmailDeliveryStatus.FAILED
        delivery.sent_at = None
        delivery.failed_at = now
        delivery.last_event_at = now
        delivery.failure_message = message[:2000]
        delivery.save(update_fields=[
            "status",
            "sent_at",
            "failed_at",
            "last_event_at",
            "failure_message",
        ])

        EmailEvent.objects.create(
            delivery=delivery,
            event_type=EmailEventType.FAILED,
            occurred_at=now,
            metadata={"message": message[:1000]},
        )

    def _refresh_totals(self, campaign):
        deliveries = EmailLog.objects.filter(campaign=campaign)

        sent_statuses = [
            EmailDeliveryStatus.SENT,
            EmailDeliveryStatus.DELIVERED,
            EmailDeliveryStatus.BOUNCED,
            EmailDeliveryStatus.COMPLAINED,
        ]

        totals = {
            "recipient_count": deliveries.values("email").distinct().count(),
            "sent_count": deliveries.filter(
                status__in=sent_statuses
            ).values("email").distinct().count(),
            "delivered_count": deliveries.filter(
                status=EmailDeliveryStatus.DELIVERED
            ).values("email").distinct().count(),
            "failed_count": deliveries.filter(
                status=EmailDeliveryStatus.FAILED
            ).values("email").distinct().count(),
            "bounced_count": deliveries.filter(
                status=EmailDeliveryStatus.BOUNCED
            ).values("email").distinct().count(),
            "complaint_count": deliveries.filter(
                status=EmailDeliveryStatus.COMPLAINED
            ).values("email").distinct().count(),
            "unique_open_count": deliveries.filter(
                opened=True
            ).values("email").distinct().count(),
            "unique_click_count": deliveries.filter(
                clicked=True
            ).values("email").distinct().count(),
        }

        aggregates = deliveries.aggregate(
            total_opens=Sum("open_count"),
            total_clicks=Sum("click_count"),
        )

        totals["open_count"] = aggregates["total_opens"] or 0
        totals["click_count"] = aggregates["total_clicks"] or 0
        totals["unsubscribe_count"] = EmailEvent.objects.filter(
            delivery__campaign=campaign,
            event_type=EmailEventType.UNSUBSCRIBED,
        ).values("delivery_id").distinct().count()

        EmailCampaign.objects.filter(pk=campaign.pk).update(**totals)

        return totals

    def _fail_campaign(self, campaign, error, *, refresh_totals=True):
        totals = (
            self._refresh_totals(campaign)
            if refresh_totals
            else {
                "recipient_count": campaign.recipient_count,
                "sent_count": campaign.sent_count,
                "failed_count": campaign.failed_count,
            }
        )

        now = timezone.now()

        EmailCampaign.objects.filter(pk=campaign.pk).update(
            status=CampaignStatus.FAILED,
            failed_at=now,
            completed_at=now,
            last_error=error[:4000],
        )

        return CampaignSendResult(
            campaign_id=campaign.id,
            targeted=totals.get("recipient_count", 0),
            sent=totals.get("sent_count", 0),
            suppressed=0,
            failed=totals.get("failed_count", 0),
            status=CampaignStatus.FAILED,
            error=error,
        )

    def _unavailable_result(self, campaign_id):
        campaign = EmailCampaign.objects.filter(pk=campaign_id).only(
            "id",
            "status",
        ).first()

        if not campaign:
            return CampaignSendResult(
                campaign_id=campaign_id,
                targeted=0,
                sent=0,
                suppressed=0,
                failed=0,
                status="missing",
                error="Campaign does not exist.",
            )

        return CampaignSendResult(
            campaign_id=campaign_id,
            targeted=0,
            sent=0,
            suppressed=0,
            failed=0,
            status=campaign.status,
            error="Campaign is not currently eligible for sending.",
        )


def send_campaign_email_batch(campaign_id):
    return CampaignDeliveryService().send(campaign_id)


def send_test_email_for_campaign(campaign):
    return CampaignDeliveryService().send_test(campaign)