# apps/notifications/signals/friendship_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profiles.models import Friendship
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Friendship, dispatch_uid="notif.friendship_v5")
def friendship_notifications(sender, instance, created, **kwargs):
    """
    Unified signal for Friendship events.

    Important:
    - Boundary / Stillness policy is enforced centrally in
      create_and_dispatch_notification().
    - Symmetric accepted friendship rows are often created after accepting
      a pending request. We skip created+accepted rows here to prevent
      duplicate acceptance notifications.
    """

    try:
        from_user = instance.from_user
        to_user = instance.to_user
        status_value = (instance.status or "").strip().lower()
        friendship_id = instance.id

        if not from_user or not to_user:
            return

        # ----------------------------------------------------
        # Prevent duplicate notification from symmetric row.
        # The real acceptance notification comes from updating
        # the original pending row to accepted.
        # ----------------------------------------------------
        if created and status_value == "accepted":
            return

        payload = {
            "friendship_id": friendship_id,
            "status": status_value,
            "relation": "friend",
        }

        # ----------------------------------------------------
        # 1) Request Sent
        # ----------------------------------------------------
        if created and status_value == "pending":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friend_request_received",
                message=(
                    f"{from_user.username} has reached out to walk this journey "
                    "together with you on TownLIT ✨"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 2) Request Accepted
        # ----------------------------------------------------
        if status_value == "accepted":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="friend_request_accepted",
                message=(
                    f"{to_user.username} accepted your connection request — "
                    "welcome to a new shared journey 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 3) Request Declined
        # ----------------------------------------------------
        if status_value == "declined":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="friend_request_declined",
                message=(
                    f"{to_user.username} wasn’t able to accept your connection "
                    "request right now."
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 4) Request Cancelled
        # ----------------------------------------------------
        if status_value == "cancelled":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friend_request_cancelled",
                message=(
                    f"{from_user.username} decided not to continue the connection "
                    "request."
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 5) Friendship Removed
        # ----------------------------------------------------
        if status_value == "deleted":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friendship_deleted",
                message=(
                    f"Paths sometimes change between you and {from_user.username}, "
                    "but your journey continues — may new connections bring light "
                    "and encouragement 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

    except Exception:
        logger.error(
            "[Friendship] Notification signal failed",
            exc_info=True,
        )