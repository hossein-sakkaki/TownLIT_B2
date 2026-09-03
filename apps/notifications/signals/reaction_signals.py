# apps/notifications/signals/reaction_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.services.presentation import build_reaction_message
from apps.notifications.services.services import create_and_dispatch_notification
from apps.posts.models.reaction import Reaction

logger = logging.getLogger(__name__)


REACTION_NOTIFICATION_TYPES = {
    "like": "new_reaction_like",
    "bless": "new_reaction_bless",
    "gratitude": "new_reaction_gratitude",
    "amen": "new_reaction_amen",
    "encouragement": "new_reaction_encouragement",
    "empathy": "new_reaction_empathy",
    "faithfire": "new_reaction_faithfire",
    "support": "new_reaction_support",
}


def _resolve_owner(obj):
    if not obj:
        return None

    for attr in (
        "user",
        "owner",
        "author",
        "created_by",
        "name",
        "member_user",
        "org_owner_user",
    ):
        value = getattr(obj, attr, None)
        if value is not None and hasattr(value, "id"):
            return value

    try:
        inner = getattr(obj, "content_object", None)
        if inner:
            for attr in ("user", "owner", "org_owner_user"):
                value = getattr(inner, attr, None)
                if value is not None and hasattr(value, "id"):
                    return value
    except Exception:
        pass

    return None


@receiver(post_save, sender=Reaction, dispatch_uid="notif.reaction.create_v6")
def on_reaction_created(sender, instance: Reaction, created, **kwargs):
    if not created:
        return

    actor = getattr(instance, "name", None)
    if not actor:
        return

    target = getattr(instance, "content_object", None)
    recipient = _resolve_owner(target)

    if not recipient or recipient.id == actor.id:
        return

    reaction_type = str(
        getattr(instance, "reaction_type", "") or ""
    ).strip().lower()

    notif_type = REACTION_NOTIFICATION_TYPES.get(
        reaction_type,
        "new_reaction",
    )

    # Never expose the private reaction message in notification copy.
    private_message = str(getattr(instance, "message", "") or "").strip()
    has_private_message = bool(private_message)

    message = build_reaction_message(
        actor,
        target,
        reaction_type,
        has_private_message,
    )

    payload = {
        "reaction_id": instance.id,
        "reaction_type": reaction_type,
        "has_message": has_private_message,
        "target_type": (
            target._meta.label_lower
            if target is not None and hasattr(target, "_meta")
            else None
        ),
        "target_id": getattr(target, "pk", None),
    }

    try:
        create_and_dispatch_notification(
            recipient=recipient,
            actor=actor,
            notif_type=notif_type,
            message=message,
            target_obj=target,
            action_obj=instance,
            extra_payload=payload,
        )
    except Exception as error:
        logger.exception(
            "[Notif] Reaction dispatch failed: %s",
            error,
        )