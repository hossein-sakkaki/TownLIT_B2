# apps/notifications/signals/comment_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.posts.models import Comment
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)

# -----------------------------------------------------
# Helper: Resolve owner (user… or nested user)
# -----------------------------------------------------
def _resolve_owner(obj):
    if not obj:
        return None

    for attr in ("user", "owner", "author", "created_by", "name", "member_user", "org_owner_user"):
        val = getattr(obj, attr, None)
        if val is not None and hasattr(val, "id"):
            return val

    try:
        if hasattr(obj, "content_object"):
            inner = obj.content_object
            for attr in ("user", "owner", "org_owner_user"):
                val = getattr(inner, attr, None)
                if val is not None and hasattr(val, "id"):
                    return val
    except Exception as e:
        logger.debug(f"[Notif] Nested resolve failed: {e}")

    return None


# -----------------------------------------------------
# Main Signal: Comment Created
# -----------------------------------------------------
@receiver(post_save, sender=Comment, dispatch_uid="notif.comment_v4")
def on_comment_created(sender, instance: Comment, created, **kwargs):

    if not created:
        return

    actor = getattr(instance, "name", None)
    if not actor:
        logger.error("⛔ SIGNAL: No actor found for comment %s", instance.id)
        return

    # Resolve target object
    try:
        target = instance.content_type.get_object_for_this_type(pk=instance.object_id)
    except Exception as e:
        logger.error("⛔ SIGNAL: target resolve failed for comment %s: %s", instance.id, e)
        target = None

    post_owner = _resolve_owner(target)

    # ----------------------------
    # Case 1 — Root Comment
    # ----------------------------
    if instance.recomment is None:
        if post_owner and post_owner.id != actor.id:
            create_and_dispatch_notification(
                recipient=post_owner,
                actor=actor,
                notif_type="new_comment",
                message=f"{actor.username} commented on your post.",
                target_obj=target,
                action_obj=instance,
                extra_payload={
                    "comment_id": instance.id,
                    "parent_id": None,
                    "is_reply": False,
                }
            )

    # ----------------------------
    # Case 2 — Reply to comment
    # ----------------------------
    else:
        parent = instance.recomment
        original_author = getattr(parent, "name", None)

        if original_author and original_author.id != actor.id:
            create_and_dispatch_notification(
                recipient=original_author,
                actor=actor,
                notif_type="new_reply",
                message=f"{actor.username} replied to your comment.",
                target_obj=parent,
                action_obj=instance,
                extra_payload={
                    "comment_id": instance.id,
                    "parent_id": parent.id,
                    "is_reply": True,
                }
            )

        try:
            parent_target = parent.content_type.get_object_for_this_type(pk=parent.object_id)
        except Exception as e:
            logger.error("⛔ SIGNAL: parent_target resolve failed %s", e)
            parent_target = None

        parent_owner = _resolve_owner(parent_target)

        if parent_owner and parent_owner.id not in (actor.id, getattr(original_author, "id", None)):
            create_and_dispatch_notification(
                recipient=parent_owner,
                actor=actor,
                notif_type="new_reply_post_owner",
                message=f"{actor.username} replied to a comment on your post.",
                target_obj=parent_target,
                action_obj=instance,
                extra_payload={
                    "comment_id": instance.id,
                    "parent_id": parent.id,
                    "is_reply": True,
                }
            )
