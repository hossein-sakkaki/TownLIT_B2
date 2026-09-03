# apps/notifications/signals/fellowship_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.services.presentation import build_fellowship_message
from apps.notifications.services.services import create_and_dispatch_notification
from apps.profiles.models import Fellowship

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Fellowship, dispatch_uid="notif.fellowship_v5")
def fellowship_notifications(sender, instance, created, **kwargs):
    """
    Centralized LITCovenant notification signal.

    Handles:
    - Request sent
    - Accepted
    - Confirmed
    - Declined
    - Cancelled

    Boundary and Stillness policy remains centralized in the
    notification delivery service.
    """
    try:
        from_user = instance.from_user
        to_user = instance.to_user

        if not from_user or not to_user:
            return

        relation = instance.fellowship_type or "fellowship"
        relation_clean = relation.capitalize()

        status_value = (instance.status or "").strip()
        status_normalized = status_value.lower()

        # Symmetric accepted rows must not create duplicate notifications.
        if created and status_normalized == "accepted":
            return

        payload = {
            "fellowship_id": instance.id,
            "status": status_value,
            "relation": relation,
            "is_covenant": True,
        }

        # LITCovenant request received.
        if created and status_normalized == "pending":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_received",
                message=build_fellowship_message(
                    "fellowship_request_received",
                    from_user,
                    relation_clean,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            return

        # LITCovenant accepted.
        if status_normalized == "accepted":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_accepted",
                message=build_fellowship_message(
                    "fellowship_request_accepted",
                    to_user,
                    relation_clean,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_confirmed",
                message=build_fellowship_message(
                    "fellowship_request_confirmed",
                    from_user,
                    relation_clean,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            return

        # LITCovenant declined.
        if status_normalized == "declined":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_declined",
                message=build_fellowship_message(
                    "fellowship_request_declined",
                    to_user,
                    relation_clean,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_decline_notice",
                message=build_fellowship_message(
                    "fellowship_decline_notice",
                    from_user,
                    relation_clean,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )
            return

        # LITCovenant cancelled.
        if status_normalized == "cancelled":
            for recipient, actor in (
                (from_user, to_user),
                (to_user, from_user),
            ):
                create_and_dispatch_notification(
                    recipient=recipient,
                    actor=actor,
                    notif_type="fellowship_cancelled",
                    message=build_fellowship_message(
                        "fellowship_cancelled",
                        actor,
                        relation_clean,
                    ),
                    target_obj=instance,
                    action_obj=instance,
                    extra_payload=payload,
                )

    except Exception:
        logger.error(
            "[LITCovenant] Fellowship signal error",
            exc_info=True,
        )