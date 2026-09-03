# apps/notifications/signals/comment_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.services.presentation import build_comment_message
from apps.notifications.services.services import create_and_dispatch_notification
from apps.posts.models.comment import Comment

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=Comment, dispatch_uid="notif.comment_v5")
def on_comment_created(sender, instance: Comment, created, **kwargs):
    if not created:
        return

    actor = getattr(instance, "name", None)
    if not actor:
        logger.error("⛔ No actor found for comment %s", instance.id)
        return

    try:
        root_target = instance.content_type.get_object_for_this_type(
            pk=instance.object_id
        )
    except Exception as error:
        logger.error(
            "⛔ Root target resolve failed for comment %s: %s",
            instance.id,
            error,
        )
        return

    post_owner = _resolve_owner(root_target)

    # Root comment.
    if instance.recomment is None:
        if post_owner and post_owner.id != actor.id:
            create_and_dispatch_notification(
                recipient=post_owner,
                actor=actor,
                notif_type="new_comment",
                message=build_comment_message(
                    "new_comment",
                    actor,
                    root_target,
                ),
                target_obj=root_target,
                action_obj=instance,
                extra_payload={
                    "comment_id": instance.id,
                    "parent_id": None,
                    "is_reply": False,
                },
            )

        return

    parent = instance.recomment
    original_author = getattr(parent, "name", None)

    # Reply to the original comment author.
    if original_author and original_author.id != actor.id:
        create_and_dispatch_notification(
            recipient=original_author,
            actor=actor,
            notif_type="new_reply",
            message=build_comment_message(
                "new_reply",
                actor,
                root_target,
            ),
            target_obj=root_target,
            action_obj=instance,
            extra_payload={
                "comment_id": instance.id,
                "parent_id": parent.id,
                "is_reply": True,
            },
        )

    # Also notify the content owner when they are a different user.
    if (
        post_owner
        and post_owner.id not in (
            actor.id,
            getattr(original_author, "id", None),
        )
    ):
        create_and_dispatch_notification(
            recipient=post_owner,
            actor=actor,
            notif_type="new_reply_post_owner",
            message=build_comment_message(
                "new_reply_post_owner",
                actor,
                root_target,
            ),
            target_obj=root_target,
            action_obj=instance,
            extra_payload={
                "comment_id": instance.id,
                "parent_id": parent.id,
                "is_reply": True,
            },
        )