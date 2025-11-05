from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.notifications.models import Notification
from apps.posts.models import Comment

import logging
logger = logging.getLogger(__name__)

# --- helpers ------------------------------------------------------------

def _resolve_target_object(ct, oid):
    """Return target object of the comment, or None on failure."""
    try:
        return ct.get_object_for_this_type(pk=oid)
    except Exception:
        logger.debug("Failed to resolve target object for comment", extra={"ct_id": ct.id if ct else None, "oid": oid})
        return None

def _resolve_author_user(obj):
    """
    Try to find a user-like field on the target object.
    Common candidates: user, owner, author, created_by, name (if FK to user).
    Return user or None.
    """
    if obj is None:
        return None
    for attr in ("user", "owner", "author", "created_by", "name"):
        val = getattr(obj, attr, None)
        # if it's a FK to user, it should have id/username
        if val is not None and hasattr(val, "id"):
            return val
    return None

def _feature_enabled():
    return getattr(settings, "ENABLE_COMMENT_NOTIFICATIONS", False)

def _safe_reverse(*args, **kwargs):
    try:
        return reverse(*args, **kwargs)
    except Exception:
        return None

# --- unified receiver ---------------------------------------------------

@receiver(post_save, sender=Comment)
def on_comment_created(sender, instance: Comment, created, **kwargs):
    # TEMP kill switch
    if not _feature_enabled():
        return

    if not created:
        return

    # Resolve target for this comment
    target = _resolve_target_object(instance.content_type, instance.object_id)
    post_author = _resolve_author_user(target)

    # Basic message/link
    link = _safe_reverse('Comment_detail', kwargs={'pk': instance.pk})
    # If your URL name differs or not ready, gracefully skip linking:
    # link = link or f"/comments/{instance.pk}"  # optional fallback

    try:
        if instance.recomment is None:
            # New root comment
            if post_author and post_author != instance.name:
                Notification.objects.create(
                    user=post_author,
                    message=f"{instance.name.username} commented on your post.",
                    notification_type='new_comment',
                    content_type=ContentType.objects.get_for_model(sender),
                    object_id=instance.id,
                    link=link
                )
        else:
            # New reply
            parent = instance.recomment
            parent_target = _resolve_target_object(parent.content_type, parent.object_id)
            parent_post_author = _resolve_author_user(parent_target)
            original_comment_author = parent.name

            if original_comment_author and original_comment_author != instance.name:
                Notification.objects.create(
                    user=original_comment_author,
                    message=f"{instance.name.username} replied to your comment.",
                    notification_type='new_recomment',
                    content_type=ContentType.objects.get_for_model(sender),
                    object_id=instance.id,
                    link=link
                )

            if parent_post_author and parent_post_author not in (instance.name, original_comment_author):
                Notification.objects.create(
                    user=parent_post_author,
                    message=f"{instance.name.username} replied to a comment on your post.",
                    notification_type='new_recomment',
                    content_type=ContentType.objects.get_for_model(sender),
                    object_id=instance.id,
                    link=link
                )
    except Exception:
        # Don't crash comment creation for notification issues
        logger.exception("Failed to create standard notifications for comment")

    # Optional: push + realtime (guarded)
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        users_to_notify = []
        if instance.recomment is None:
            if post_author and post_author != instance.name:
                users_to_notify.append(post_author)
        else:
            parent = instance.recomment
            parent_target = _resolve_target_object(parent.content_type, parent.object_id)
            parent_post_author = _resolve_author_user(parent_target)
            original_comment_author = parent.name

            if original_comment_author and original_comment_author != instance.name:
                users_to_notify.append(original_comment_author)
            if parent_post_author and parent_post_author not in (instance.name, original_comment_author):
                users_to_notify.append(parent_post_author)

        for user in users_to_notify:
            # real-time WS
            try:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {
                        "type": "send_notification",
                        "message": (
                            f"{instance.name.username} commented on your post."
                            if instance.recomment is None
                            else f"{instance.name.username} replied to your comment."
                        ),
                    }
                )
            except Exception:
                logger.debug("WS notify failed (ignored)", exc_info=True)
    except Exception:
        logger.debug("Realtime notify section failed (ignored)", exc_info=True)
