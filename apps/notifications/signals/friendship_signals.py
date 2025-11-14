# apps/notifications/signals/friendship_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.profiles.models import Friendship
from apps.notifications.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Friendship)
def friendship_notifications(sender, instance, created, **kwargs):
    """
    Unified signal for all Friendship events.
    Handles DB + WS + Push + Email through centralized service.
    """

    try:
        # 🔹 1. Friend request sent
        if created and instance.status == "pending":
            create_and_dispatch_notification(
                recipient=instance.to_user,
                actor=instance.from_user,
                notif_type="friend_request_received",
                message=f"{instance.from_user.username} sent you a friend request.",
                target_obj=instance,
                link=getattr(instance, "get_absolute_url", lambda: None)(),
            )
            logger.debug(f"[Friendship] Friend request sent → user {instance.to_user_id}")

        # 🔹 2. Friend request accepted
        elif instance.status == "accepted":
            create_and_dispatch_notification(
                recipient=instance.from_user,
                actor=instance.to_user,
                notif_type="friend_request_accepted",
                message=f"{instance.to_user.username} accepted your friend request.",
                target_obj=instance,
                link=getattr(instance, "get_absolute_url", lambda: None)(),
            )
            logger.debug(f"[Friendship] Friend request accepted → user {instance.from_user_id}")

        # 🔹 3. Friend request declined
        elif instance.status == "declined":
            create_and_dispatch_notification(
                recipient=instance.from_user,
                actor=instance.to_user,
                notif_type="friend_request_declined",
                message=f"{instance.to_user.username} declined your friend request.",
                target_obj=instance,
                link=getattr(instance, "get_absolute_url", lambda: None)(),
            )
            logger.debug(f"[Friendship] Friend request declined → user {instance.from_user_id}")

        # 🔹 4. Friendship cancelled (user withdrew request before response)
        elif instance.status == "cancelled":
            create_and_dispatch_notification(
                recipient=instance.to_user,
                actor=instance.from_user,
                notif_type="friend_request_cancelled",
                message=f"{instance.from_user.username} cancelled their friend request.",
                target_obj=instance,
                link=getattr(instance, "get_absolute_url", lambda: None)(),
            )
            logger.debug(f"[Friendship] Friend request cancelled → user {instance.to_user_id}")

        # 🔹 5. Friendship deleted (unfriend)
        elif instance.status == "deleted":
            create_and_dispatch_notification(
                recipient=instance.to_user,
                actor=instance.from_user,
                notif_type="friendship_deleted",
                message=f"{instance.from_user.username} removed you from their friend list.",
                target_obj=instance,
                link=getattr(instance, "get_absolute_url", lambda: None)(),
            )
            logger.debug(f"[Friendship] Friendship deleted → user {instance.to_user_id}")

    except Exception as e:
        logger.error(f"[Friendship] Notification signal failed: {e}", exc_info=True)
