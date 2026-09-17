# apps/notifications/campaigns/publisher.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.notifications.constants import (
    CHANNEL_EMAIL,
    CHANNEL_PUSH,
    CHANNEL_WS,
)
from apps.notifications.models import (
    Notification,
    NotificationCampaign,
    NotificationCampaignDelivery,
)
from apps.notifications.services.services import (
    deliver_existing_notification,
)

from .audience import (
    push_platforms_for_campaign,
    resolve_campaign_audience,
)


logger = logging.getLogger(__name__)

CAMPAIGN_BATCH_SIZE = 250


def _chunks(values, size):
    chunk = []

    for value in values:
        chunk.append(value)

        if len(chunk) >= size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk


def _delivery_channels(campaign: NotificationCampaign) -> int:
    # In-app campaigns always receive realtime delivery.
    channels = CHANNEL_WS

    if campaign.send_push:
        channels |= CHANNEL_PUSH

    if campaign.send_email:
        channels |= CHANNEL_EMAIL

    return channels


def queue_campaign(campaign: NotificationCampaign) -> NotificationCampaign:
    """Validate and queue a campaign."""
    campaign.full_clean()

    if (
        campaign.audience_type == NotificationCampaign.Audience.SELECTED
        and not campaign.selected_users.exists()
    ):
        raise ValidationError(
            "Selected Users audience requires at least one user."
        )

    with transaction.atomic():
        locked = NotificationCampaign.objects.select_for_update().get(
            pk=campaign.pk
        )

        if locked.status not in {
            NotificationCampaign.Status.DRAFT,
            NotificationCampaign.Status.FAILED,
        }:
            raise ValidationError(
                "Only Draft or Failed campaigns can be queued."
            )

        locked.last_error = ""
        locked.completed_at = None

        if locked.scheduled_at and locked.scheduled_at > timezone.now():
            locked.status = NotificationCampaign.Status.SCHEDULED
            locked.save(
                update_fields=[
                    "status",
                    "last_error",
                    "completed_at",
                    "updated_at",
                ]
            )

            return locked

        locked.status = NotificationCampaign.Status.QUEUED
        locked.save(
            update_fields=[
                "status",
                "last_error",
                "completed_at",
                "updated_at",
            ]
        )

        from apps.notifications.tasks import publish_notification_campaign

        transaction.on_commit(
            lambda: publish_notification_campaign.delay(
                locked.id
            )
        )

        return locked


def queue_due_campaign(campaign_id: int) -> bool:
    """Queue one due scheduled campaign."""
    with transaction.atomic():
        campaign = (
            NotificationCampaign.objects
            .select_for_update()
            .filter(
                pk=campaign_id,
                status=NotificationCampaign.Status.SCHEDULED,
                scheduled_at__lte=timezone.now(),
            )
            .first()
        )

        if not campaign:
            return False

        campaign.status = NotificationCampaign.Status.QUEUED
        campaign.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        from apps.notifications.tasks import publish_notification_campaign

        transaction.on_commit(
            lambda: publish_notification_campaign.delay(
                campaign.id
            )
        )

    return True


def prepare_and_dispatch_campaign(campaign_id: int) -> None:
    """Snapshot the audience and fan out Celery batches."""
    with transaction.atomic():
        campaign = NotificationCampaign.objects.select_for_update().get(
            pk=campaign_id
        )

        if campaign.status == NotificationCampaign.Status.CANCELLED:
            return

        if campaign.status not in {
            NotificationCampaign.Status.QUEUED,
            NotificationCampaign.Status.SENDING,
        }:
            return

        campaign.status = NotificationCampaign.Status.SENDING

        if campaign.published_at is None:
            campaign.published_at = timezone.now()

        campaign.save(
            update_fields=[
                "status",
                "published_at",
                "updated_at",
            ]
        )

    # Keep an existing snapshot when retrying a failed campaign.
    if not NotificationCampaignDelivery.objects.filter(
        campaign_id=campaign_id
    ).exists():
        audience_ids = (
            resolve_campaign_audience(campaign)
            .order_by("pk")
            .values_list("pk", flat=True)
            .iterator(chunk_size=1000)
        )

        for user_ids in _chunks(
            audience_ids,
            CAMPAIGN_BATCH_SIZE,
        ):
            NotificationCampaignDelivery.objects.bulk_create(
                [
                    NotificationCampaignDelivery(
                        campaign_id=campaign_id,
                        user_id=user_id,
                    )
                    for user_id in user_ids
                ],
                ignore_conflicts=True,
                batch_size=CAMPAIGN_BATCH_SIZE,
            )

    total = NotificationCampaignDelivery.objects.filter(
        campaign_id=campaign_id
    ).count()

    NotificationCampaign.objects.filter(
        pk=campaign_id
    ).update(
        total_recipients=total,
    )

    if total == 0:
        NotificationCampaign.objects.filter(
            pk=campaign_id
        ).update(
            status=NotificationCampaign.Status.SENT,
            completed_at=timezone.now(),
        )
        return

    delivery_ids = (
        NotificationCampaignDelivery.objects
        .filter(
            campaign_id=campaign_id,
            status__in=[
                NotificationCampaignDelivery.Status.PENDING,
                NotificationCampaignDelivery.Status.FAILED,
            ],
        )
        .order_by("pk")
        .values_list("pk", flat=True)
        .iterator(chunk_size=1000)
    )

    from apps.notifications.tasks import deliver_notification_campaign_batch

    dispatched = False

    for ids in _chunks(
        delivery_ids,
        CAMPAIGN_BATCH_SIZE,
    ):
        dispatched = True
        deliver_notification_campaign_batch.delay(
            campaign_id,
            ids,
        )

    if not dispatched:
        refresh_campaign_metrics(
            campaign_id
        )


def deliver_campaign_batch(
    campaign_id: int,
    delivery_ids: list[int],
) -> None:
    """Deliver one campaign batch."""
    campaign = NotificationCampaign.objects.get(
        pk=campaign_id
    )

    if campaign.status == NotificationCampaign.Status.CANCELLED:
        return

    deliveries = (
        NotificationCampaignDelivery.objects
        .select_related("user")
        .filter(
            campaign_id=campaign_id,
            pk__in=delivery_ids,
            status__in=[
                NotificationCampaignDelivery.Status.PENDING,
                NotificationCampaignDelivery.Status.FAILED,
            ],
        )
        .order_by("pk")
    )

    for delivery in deliveries:
        if NotificationCampaign.objects.filter(
            pk=campaign_id,
            status=NotificationCampaign.Status.CANCELLED,
        ).exists():
            break

        _deliver_campaign_to_recipient(
            campaign=campaign,
            delivery=delivery,
        )

    refresh_campaign_metrics(
        campaign_id
    )


def _deliver_campaign_to_recipient(
    *,
    campaign: NotificationCampaign,
    delivery: NotificationCampaignDelivery,
) -> None:
    """Deliver one campaign to one account."""
    now = timezone.now()

    try:
        metadata = {
            "is_campaign": True,
            "campaign_id": campaign.id,
            "campaign_category": campaign.category,
            "action_type": campaign.action_type,
            "action_label": campaign.action_label,
            "action_url": campaign.action_url,
        }

        notification, _ = Notification.objects.get_or_create(
            campaign=campaign,
            user=delivery.user,
            defaults={
                "title": campaign.title,
                "message": campaign.message,
                "notification_type": campaign.notification_type,
                "link": campaign.action_url or None,
                "action_label": campaign.action_label,
                "metadata": metadata,
                "dedupe_key": f"campaign:{campaign.id}:user:{delivery.user_id}",
            },
        )

        result = deliver_existing_notification(
            notification,
            channels_mask=_delivery_channels(campaign),
            extra_payload=metadata,
            push_platforms=push_platforms_for_campaign(campaign),
            push_title=campaign.title,
            push_body=campaign.message,
            email_subject=campaign.title,
        )

        delivery.notification = notification
        delivery.status = NotificationCampaignDelivery.Status.SENT
        delivery.push_sent = bool(
            result.get("firebase_sent")
            or result.get("apns_sent")
        )
        delivery.email_queued = bool(
            result.get("email_queued")
        )
        delivery.error_message = ""
        delivery.processed_at = now

        delivery.save(
            update_fields=[
                "notification",
                "status",
                "push_sent",
                "email_queued",
                "error_message",
                "processed_at",
            ]
        )

    except Exception as error:
        logger.exception(
            "[Campaign] Delivery failed campaign=%s user=%s",
            campaign.id,
            delivery.user_id,
        )

        delivery.status = NotificationCampaignDelivery.Status.FAILED
        delivery.error_message = str(error)[:2000]
        delivery.processed_at = now

        delivery.save(
            update_fields=[
                "status",
                "error_message",
                "processed_at",
            ]
        )


def refresh_campaign_metrics(campaign_id: int) -> None:
    """Refresh campaign delivery counters."""
    metrics = NotificationCampaignDelivery.objects.filter(
        campaign_id=campaign_id
    ).aggregate(
        total=Count("id"),
        processed=Count(
            "id",
            filter=Q(
                status__in=[
                    NotificationCampaignDelivery.Status.SENT,
                    NotificationCampaignDelivery.Status.FAILED,
                    NotificationCampaignDelivery.Status.SKIPPED,
                ]
            ),
        ),
        in_app=Count(
            "id",
            filter=Q(notification__isnull=False),
        ),
        push_sent=Count(
            "id",
            filter=Q(push_sent=True),
        ),
        email_queued=Count(
            "id",
            filter=Q(email_queued=True),
        ),
        failed=Count(
            "id",
            filter=Q(
                status=NotificationCampaignDelivery.Status.FAILED
            ),
        ),
    )

    total = int(metrics["total"] or 0)
    processed = int(metrics["processed"] or 0)
    failed = int(metrics["failed"] or 0)

    updates = {
        "total_recipients": total,
        "processed_count": processed,
        "in_app_count": int(metrics["in_app"] or 0),
        "push_sent_count": int(metrics["push_sent"] or 0),
        "email_queued_count": int(metrics["email_queued"] or 0),
        "failed_count": failed,
    }

    campaign = NotificationCampaign.objects.filter(
        pk=campaign_id
    ).first()

    if not campaign:
        return

    if (
        campaign.status != NotificationCampaign.Status.CANCELLED
        and total > 0
        and processed >= total
    ):
        updates["status"] = (
            NotificationCampaign.Status.FAILED
            if failed
            else NotificationCampaign.Status.SENT
        )
        updates["completed_at"] = timezone.now()

    NotificationCampaign.objects.filter(
        pk=campaign_id
    ).update(**updates)


def send_campaign_preview_to_user(
    campaign: NotificationCampaign,
    user,
):
    """Send a real test notification without publishing the campaign."""
    metadata = {
        "is_campaign": True,
        "campaign_preview": True,
        "campaign_id": campaign.id,
        "campaign_category": campaign.category,
        "action_type": campaign.action_type,
        "action_label": campaign.action_label,
        "action_url": campaign.action_url,
    }

    notification = Notification.objects.create(
        user=user,
        title=f"[Test] {campaign.title}",
        message=campaign.message,
        notification_type=campaign.notification_type,
        link=campaign.action_url or None,
        action_label=campaign.action_label,
        metadata=metadata,
    )

    return deliver_existing_notification(
        notification,
        channels_mask=_delivery_channels(campaign),
        extra_payload=metadata,
        push_platforms=push_platforms_for_campaign(campaign),
        push_title=f"[Test] {campaign.title}",
        push_body=campaign.message,
        email_subject=f"[Test] {campaign.title}",
    )