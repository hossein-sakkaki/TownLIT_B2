# apps/notifications/signals/fellowship_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.profiles.models import Fellowship
from apps.notifications.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Fellowship)
def fellowship_notifications(sender, instance, created, **kwargs):
    """
    Centralized signal for all Fellowship relationship events.
    Triggers notifications for:
      - A new request is sent
      - A request is accepted
      - A request is declined
      - A fellowship is cancelled (removed)
    """

    try:
        from_user = instance.from_user
        to_user = instance.to_user
        relation = instance.fellowship_type.lower()
        link = getattr(instance, "get_absolute_url", lambda: "/lit/")()

        # --- 1️⃣ Fellowship Request Sent ---
        if created and instance.status == "Pending":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_received",
                message=f"{from_user.username} requested a {relation} relationship with you.",
                target_obj=instance,
                link=link,
            )
            logger.debug(f"[Fellowship] Pending → sent by {from_user.username}")

        # --- 2️⃣ Fellowship Accepted ---
        elif instance.status == "Accepted":
            # Notify sender that request was accepted
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_accepted",
                message=f"{to_user.username} accepted your {relation} request.",
                target_obj=instance,
                link=link,
            )

            # Notify receiver as confirmation
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_confirmed",
                message=f"You are now connected with {from_user.username} as {relation}.",
                target_obj=instance,
                link=link,
            )
            logger.debug(f"[Fellowship] Accepted → {from_user.username} & {to_user.username}")

        # --- 3️⃣ Fellowship Declined ---
        elif instance.status == "Declined":
            # notify sender that request was declined
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_declined",
                message=f"{to_user.username} declined your {relation} request.",
                target_obj=instance,
                link=link,
            )

            # optional courtesy notification to receiver
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_decline_notice",
                message=f"You declined the {relation} request from {from_user.username}.",
                target_obj=instance,
                link=link,
            )
            logger.debug(f"[Fellowship] Declined → {from_user.username} & {to_user.username}")

        # --- 4️⃣ Fellowship Cancelled (removed by either side) ---
        elif instance.status == "Cancelled":
            # Notify both users (mirrored, with correct actor)
            for recipient, actor in [(from_user, to_user), (to_user, from_user)]:
                create_and_dispatch_notification(
                    recipient=recipient,
                    actor=actor,
                    notif_type="fellowship_cancelled",
                    message=f"The fellowship connection between you and {actor.username} was removed.",
                    target_obj=instance,
                    link=link,
                )
            logger.debug(f"[Fellowship] Cancelled → {from_user.username} & {to_user.username}")

    except Exception as e:
        logger.error(f"[Fellowship] Notification signal failed: {e}", exc_info=True)
