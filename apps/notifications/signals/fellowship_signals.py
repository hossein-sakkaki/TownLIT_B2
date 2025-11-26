import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profiles.models import Fellowship
from apps.notifications.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Fellowship, dispatch_uid="notif.fellowship_v4")
def fellowship_notifications(sender, instance, created, **kwargs):
    """
    Centralized LITCovenant (Fellowship) notification signal.
    Handles:
        - Request Sent
        - Accepted
        - Confirmed
        - Declined
        - Cancelled

    Produces unified deep-link payloads and supports push/email/ws channels.
    """
    try:
        from_user = instance.from_user
        to_user = instance.to_user

        relation = instance.fellowship_type or "fellowship"
        relation_clean = relation.capitalize()

        status = instance.status
        fellowship_id = instance.id

        # Unified payload for frontend (Web + Mobile)
        payload = {
            "fellowship_id": fellowship_id,
            "status": status,
            "relation": relation,
            "is_covenant": True,
        }

        # ---------------------------------------------
        # 1️⃣ Fellowship Request Sent
        # ---------------------------------------------
        if created and status == "Pending":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_received",
                message=f"{from_user.username} invited you into a LITCovenant ({relation_clean}).",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            logger.debug(f"[LITCovenant] Pending → sent by {from_user.username}")
            return

        # ---------------------------------------------
        # 2️⃣ Fellowship Accepted
        # ---------------------------------------------
        if status == "Accepted":

            # Notify requester
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_accepted",
                message=f"{to_user.username} accepted your LITCovenant request ({relation_clean}).",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            # Notify accepter (confirmation)
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_confirmed",
                message=f"You are now connected with {from_user.username} under a LITCovenant ({relation_clean}).",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            logger.debug(f"[LITCovenant] Accepted → {from_user.username} & {to_user.username}")
            return

        # ---------------------------------------------
        # 3️⃣ Fellowship Declined
        # ---------------------------------------------
        if status == "Declined":

            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_declined",
                message=f"{to_user.username} declined your LITCovenant request ({relation_clean}).",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_decline_notice",
                message=f"You declined the LITCovenant request from {from_user.username}.",
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            logger.debug(f"[LITCovenant] Declined → {from_user.username} & {to_user.username}")
            return

        # ---------------------------------------------
        # 4️⃣ Fellowship Cancelled
        # ---------------------------------------------
        if status == "Cancelled":

            # notify both (mirrored)
            for recipient, actor in [(from_user, to_user), (to_user, from_user)]:
                create_and_dispatch_notification(
                    recipient=recipient,
                    actor=actor,
                    notif_type="fellowship_cancelled",
                    message=f"The LITCovenant between you and {actor.username} was cancelled.",
                    target_obj=instance,
                    action_obj=instance,
                    extra_payload=payload,
                )

            logger.debug(f"[LITCovenant] Cancelled → {from_user.username} & {to_user.username}")
            return

    except Exception as e:
        logger.error(f"[LITCovenant] Fellowship signal error: {e}", exc_info=True)
