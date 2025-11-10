# apps/notifications/signals/comment_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.posts.models import Comment
from apps.notifications.services import create_and_dispatch_notification

def _resolve_owner(obj):
    for attr in ("user", "owner", "author", "created_by", "name"):
        v = getattr(obj, attr, None)
        if v is not None and hasattr(v, "id"):
            return v
    return None

@receiver(post_save, sender=Comment, dispatch_uid="notif_on_comment_create_v1")
def on_comment_created(sender, instance: Comment, created, **kwargs):
    if not created:
        return

    actor = getattr(instance, "name", None)  # author FK (CustomUser)
    if not actor:
        return

    target = None
    try:
        # Comment has (content_type, object_id)
        target = instance.content_type.get_object_for_this_type(pk=instance.object_id)
    except Exception:
        target = None

    post_owner = _resolve_owner(target)

    # Build link to comment detail if available
    link = None
    try:
        if hasattr(instance, "get_absolute_url"):
            link = instance.get_absolute_url()
    except Exception:
        pass

    if instance.recomment is None:
        # Root comment on a post-like object
        if post_owner and post_owner.id != actor.id:
            create_and_dispatch_notification(
                recipient=post_owner,
                actor=actor,
                notif_type="new_comment",
                message=f"{actor.username} commented on your post.",
                target_obj=target,
                action_obj=instance,
                link=link,
            )
    else:
        # Reply to another comment
        parent = instance.recomment
        original_comment_author = getattr(parent, "name", None)

        # Notify original comment author (not self)
        if original_comment_author and original_comment_author.id != actor.id:
            create_and_dispatch_notification(
                recipient=original_comment_author,
                actor=actor,
                notif_type="new_reply",
                message=f"{actor.username} replied to your comment.",
                target_obj=parent,          # target = parent comment thread
                action_obj=instance,        # action = new reply
                link=link,
            )

        # Optionally notify post owner if distinct from both
        parent_target = None
        try:
            parent_target = parent.content_type.get_object_for_this_type(pk=parent.object_id)
        except Exception:
            parent_target = None

        parent_post_owner = _resolve_owner(parent_target)
        if parent_post_owner and parent_post_owner.id not in (actor.id, getattr(original_comment_author, "id", None)):
            create_and_dispatch_notification(
                recipient=parent_post_owner,
                actor=actor,
                notif_type="new_reply",
                message=f"{actor.username} replied to a comment on your post.",
                target_obj=parent_target,
                action_obj=instance,
                link=link,
            )
