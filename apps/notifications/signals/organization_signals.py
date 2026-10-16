# apps/notifications/signals/organization_signals.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.services.organization_publisher import (
    publish_organization_audit_notification,
    publish_subscription_event_notification,
)
from apps.organizations.models import OrganizationAuditLog
from apps.subscriptions.models import SubscriptionEvent


logger = logging.getLogger(__name__)


def _safe_publish(callback, **kwargs):
    try:
        callback(**kwargs)
    except Exception:
        logger.error(
            "[OrganizationNotifications] publication failed callback=%s",
            getattr(callback, "__name__", str(callback)),
            exc_info=True,
        )


@receiver(
    post_save,
    sender=OrganizationAuditLog,
    dispatch_uid="notifications.organization_audit.v1",
)
def organization_audit_notification_signal(
    sender,
    instance,
    created,
    **kwargs,
):
    if not created:
        return

    audit_log_id = instance.pk
    transaction.on_commit(
        lambda: _safe_publish(
            publish_organization_audit_notification,
            audit_log_id=audit_log_id,
        )
    )


@receiver(
    post_save,
    sender=SubscriptionEvent,
    dispatch_uid="notifications.organization_subscription_event.v1",
)
def organization_subscription_notification_signal(
    sender,
    instance,
    created,
    **kwargs,
):
    if not created:
        return

    event_id = instance.pk
    transaction.on_commit(
        lambda: _safe_publish(
            publish_subscription_event_notification,
            event_id=event_id,
        )
    )
