# apps/notifications/signals/fellowship_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profiles.models import Fellowship
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Fellowship, dispatch_uid="notif.fellowship_v5")
def fellowship_notifications(sender, instance, created, **kwargs):
    """
    Centralized LITCovenant notification signal.

    Handles:
    - Request Sent
    - Accepted
    - Confirmed
    - Declined
    - Cancelled

    Important:
    - Boundary / Stillness policy is enforced centrally in
      create_and_dispatch_notification().
    - Symmetric accepted Fellowship rows are often created after accepting
      the original pending request. We skip created+Accepted rows to avoid
      duplicate notifications.
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
        fellowship_id = instance.id

        # ----------------------------------------------------
        # Prevent duplicate notifications from symmetric rows.
        # The original pending row becomes Accepted and sends
        # the canonical notification pair.
        # ----------------------------------------------------
        if created and status_normalized == "accepted":
            logger.debug(
                "[LITCovenant] Created accepted symmetric row skipped → %s -> %s (%s)",
                from_user.id,
                to_user.id,
                relation,
            )
            return

        payload = {
            "fellowship_id": fellowship_id,
            "status": status_value,
            "relation": relation,
            "is_covenant": True,
        }

        # ----------------------------------------------------
        # 1) Fellowship Request Sent
        # ----------------------------------------------------
        if created and status_normalized == "pending":
            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_received",
                message=(
                    f"{from_user.username} has invited you into a LITCovenant "
                    f"as your {relation_clean} — a step toward trust, care, "
                    "and shared journey 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            logger.debug(
                "[LITCovenant] Pending → from=%s to=%s",
                from_user.id,
                to_user.id,
            )
            return

        # ----------------------------------------------------
        # 2) Fellowship Accepted
        # ----------------------------------------------------
        if status_normalized == "accepted":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_accepted",
                message=(
                    f"{to_user.username} has accepted your LITCovenant as "
                    f"{relation_clean} — may this relationship be filled with "
                    "grace and purpose 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_request_confirmed",
                message=(
                    f"You are now connected with {from_user.username} as "
                    f"{relation_clean} in a LITCovenant — may this bond grow "
                    "in wisdom, love, and faith 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            logger.debug(
                "[LITCovenant] Accepted → %s & %s",
                from_user.id,
                to_user.id,
            )
            return

        # ----------------------------------------------------
        # 3) Fellowship Declined
        # ----------------------------------------------------
        if status_normalized == "declined":
            create_and_dispatch_notification(
                recipient=from_user,
                actor=to_user,
                notif_type="fellowship_request_declined",
                message=(
                    f"{to_user.username} has chosen not to continue the "
                    f"LITCovenant as {relation_clean}. Every season has its "
                    "own timing — keep walking forward in peace 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            create_and_dispatch_notification(
                recipient=to_user,
                actor=from_user,
                notif_type="fellowship_decline_notice",
                message=(
                    f"You chose not to enter the LITCovenant with "
                    f"{from_user.username} as {relation_clean}. Thank you for "
                    "responding thoughtfully and with clarity 🤍"
                ),
                target_obj=instance,
                action_obj=instance,
                extra_payload=payload,
            )

            logger.debug(
                "[LITCovenant] Declined → %s & %s",
                from_user.id,
                to_user.id,
            )
            return

        # ----------------------------------------------------
        # 4) Fellowship Cancelled / Removed
        # ----------------------------------------------------
        if status_normalized == "cancelled":
            for recipient, actor in (
                (from_user, to_user),
                (to_user, from_user),
            ):
                create_and_dispatch_notification(
                    recipient=recipient,
                    actor=actor,
                    notif_type="fellowship_cancelled",
                    message=(
                        f"The LITCovenant between you and {actor.username} "
                        f"as {relation_clean} has come to a close. Paths may "
                        "change, but every step still carries meaning 🤍"
                    ),
                    target_obj=instance,
                    action_obj=instance,
                    extra_payload=payload,
                )

            logger.debug(
                "[LITCovenant] Cancelled → %s & %s",
                from_user.id,
                to_user.id,
            )
            return

    except Exception:
        logger.error(
            "[LITCovenant] Fellowship signal error",
            exc_info=True,
        )