# apps/notifications/signals/friendship_signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profiles.models import Friendship
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Friendship, dispatch_uid="notif.friendship_v4")
def friendship_notifications(sender, instance, created, **kwargs):
    """
    Unified signal for all Friendship events.
    Handles WS + Push + Email through Notification Engine.
    """

    try:
        from_user = instance.from_user
        to_user = instance.to_user
        status = instance.status.lower()
        friendship_id = instance.id

        # unified payload for frontend
        payload = {
            "friendship_id": friendship_id,
            "status": status,
            "relation": "friend",
        } 

        # ----------------------------------------------------
        # 1️⃣ Request Sent
        # ----------------------------------------------------
        if created and status == "pending":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friend_request_received",
                message=f"{from_user.username} has reached out to walk this journey together with you on TownLIT ✨",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            logger.debug(f"[Friendship] Request sent → {to_user.username}")
            return

        # ----------------------------------------------------
        # 2️⃣ Request Accepted
        # ----------------------------------------------------
        if status == "accepted":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="friend_request_accepted",
                message=f"{to_user.username} accepted your connection request — welcome to a new shared journey 🤍",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            logger.debug(f"[Friendship] Accepted → {from_user.username}")
            return

        # ----------------------------------------------------
        # 3️⃣ Request Declined
        # ----------------------------------------------------
        if status == "declined":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="friend_request_declined",
                message=f"{to_user.username} wasn’t able to accept your connection request right now.",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            logger.debug(f"[Friendship] Declined → {from_user.username}")
            return

        # ----------------------------------------------------
        # 4️⃣ Request Cancelled
        # ----------------------------------------------------
        if status == "cancelled":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friend_request_cancelled",
                message=f"{from_user.username} decided not to continue the connection request.",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            logger.debug(f"[Friendship] Cancelled → {to_user.username}")
            return

        # ----------------------------------------------------
        # 5️⃣ Friendship Removed (Unfriend)
        # ----------------------------------------------------
        if status == "deleted":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friendship_deleted",
                message=f"Paths sometimes change between you and {from_user.username}, but your journey continues — may new connections bring light and encouragement 🤍",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            logger.debug(f"[Friendship] Deleted → {to_user.username}")
            return

    except Exception as e:
        logger.error(f"[Friendship] Notification signal failed: {e}", exc_info=True)
