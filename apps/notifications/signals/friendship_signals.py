# apps/notifications/signals/friendship_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.services.services import (
    create_and_dispatch_notification,
)
from apps.profiles.models import Friendship
from apps.notifications.services.presentation import build_friendship_message

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=Friendship,
    dispatch_uid="notif.friendship_v6",
)
def friendship_notifications(
    sender,
    instance,
    created,
    **kwargs,
):
    """
    Dispatch notifications for friendship events.

    Notes:
    - Boundary policy is enforced by the notification service.
    - Created symmetric accepted rows are ignored.
    - Pending requests use the model deep link with request details.
    """

    try:
        from_user = instance.from_user
        to_user = instance.to_user

        status_value = (
            instance.status or ""
        ).strip().lower()

        friendship_id = instance.id

        if not from_user or not to_user:
            return

        # Skip the symmetric accepted row.
        if created and status_value == "accepted":
            return

        base_payload = {
            "friendship_id": friendship_id,
            "request_id": friendship_id,
            "status": status_value,
            "relation": "friend",
            "from_user_id": from_user.id,
            "to_user_id": to_user.id,
            "from_username": from_user.username,
            "to_username": to_user.username,
        }

        # ----------------------------------------------------
        # 1) Request received
        # ----------------------------------------------------
        if created and status_value == "pending":
            payload = {
                **base_payload,
                "tab": "requests",
                "request_kind": "received",
                "direction": "incoming",
            }

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friend_request_received",
                message=build_friendship_message(
                    "friend_request_received",
                    from_user,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 2) Request accepted
        # ----------------------------------------------------
        if status_value == "accepted":
            payload = {
                **base_payload,
                "request_kind": "sent",
                "direction": "outgoing",
            }

            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="friend_request_accepted",
                message=build_friendship_message(
                    "friend_request_accepted",
                    to_user,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 3) Request declined
        # ----------------------------------------------------
        if status_value == "declined":
            payload = {
                **base_payload,
                "request_kind": "sent",
                "direction": "outgoing",
            }

            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="friend_request_declined",
                message=build_friendship_message(
                    "friend_request_declined",
                    to_user,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 4) Request cancelled
        # ----------------------------------------------------
        if status_value == "cancelled":
            payload = {
                **base_payload,
                "request_kind": "received",
                "direction": "incoming",
            }

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friend_request_cancelled",
                message=build_friendship_message(
                    "friend_request_cancelled",
                    from_user,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

        # ----------------------------------------------------
        # 5) Friendship removed
        # ----------------------------------------------------
        if status_value == "deleted":
            payload = {
                **base_payload,
                "direction": "relationship",
            }

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="friendship_deleted",
                message=build_friendship_message(
                    "friendship_deleted",
                    from_user,
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            return

    except Exception:
        logger.exception(
            "[Friendship] Notification signal failed"
        )