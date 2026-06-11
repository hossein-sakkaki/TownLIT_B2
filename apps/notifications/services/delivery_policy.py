# apps/notifications/services/delivery_policy.py

from __future__ import annotations

import logging
from dataclasses import dataclass

from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.notifications.constants import (
    CHANNEL_WS,
    CHANNEL_PUSH,
    CHANNEL_EMAIL,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationDeliveryDecision:
    """
    Final notification delivery decision.

    persist:
        Whether to create the Notification DB row.

    channels_mask:
        Final allowed channels after Boundary/Stillness filtering.

    reason:
        Internal reason for logs/debugging only.
    """
    persist: bool
    channels_mask: int
    reason: str = ""


def apply_relationship_delivery_policy(
    *,
    recipient,
    actor,
    channels_mask: int,
) -> NotificationDeliveryDecision:
    """
    Apply TownLIT relational safety policy to notifications.

    Boundary:
        No notification should be created or delivered.

    Stillness:
        Keep the in-app notification record,
        but suppress interruptive channels:
        - WebSocket
        - Push
        - Email

    No actor:
        System notifications are allowed as-is.
    """

    if not recipient:
        return NotificationDeliveryDecision(
            persist=False,
            channels_mask=0,
            reason="missing_recipient",
        )

    if not actor:
        return NotificationDeliveryDecision(
            persist=True,
            channels_mask=channels_mask,
            reason="system_or_actorless_notification",
        )

    if getattr(actor, "id", None) == getattr(recipient, "id", None):
        return NotificationDeliveryDecision(
            persist=False,
            channels_mask=0,
            reason="self_notification_suppressed",
        )

    # Boundary is stronger than Stillness.
    try:
        if BoundaryPolicy.has_boundary_between(actor, recipient):
            return NotificationDeliveryDecision(
                persist=False,
                channels_mask=0,
                reason="boundary_suppressed",
            )
    except Exception:
        logger.warning(
            "[NotifPolicy] Boundary check failed actor=%s recipient=%s",
            getattr(actor, "id", None),
            getattr(recipient, "id", None),
            exc_info=True,
        )

    # Stillness should suppress interruption, but keep in-app history.
    try:
        can_notify = BoundaryPolicy.can_notify(
            actor=actor,
            recipient=recipient,
        )

        if not can_notify:
            quiet_mask = channels_mask & ~(CHANNEL_WS | CHANNEL_PUSH | CHANNEL_EMAIL)

            return NotificationDeliveryDecision(
                persist=True,
                channels_mask=quiet_mask,
                reason="stillness_quiet_delivery",
            )

    except Exception:
        logger.warning(
            "[NotifPolicy] can_notify check failed actor=%s recipient=%s",
            getattr(actor, "id", None),
            getattr(recipient, "id", None),
            exc_info=True,
        )

    return NotificationDeliveryDecision(
        persist=True,
        channels_mask=channels_mask,
        reason="allowed",
    )