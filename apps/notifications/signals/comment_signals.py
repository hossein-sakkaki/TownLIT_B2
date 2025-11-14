import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.posts.models import Comment
from apps.notifications.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


# --- Helper to find possible user owner of an object ---------------------
def _resolve_owner(obj):
    """
    Find likely user-owner from various object types (User, Member, Organization, etc.).
    Handles nested (polymorphic) ownership like Testimony → Member → User.
    """
    if not obj:
        return None

    # Direct user or common fields
    for attr in ("user", "owner", "author", "created_by", "name", "member_user", "org_owner_user"):
        val = getattr(obj, attr, None)
        if val is not None and hasattr(val, "id"):
            return val

    # --- Handle nested generic ownerships ---
    try:
        if hasattr(obj, "content_object"):
            inner = obj.content_object
            if hasattr(inner, "user") and inner.user:
                return inner.user
            for attr in ("owner", "org_owner_user"):
                val = getattr(inner, attr, None)
                if val is not None and hasattr(val, "id"):
                    return val
    except Exception as e:
        logger.debug(f"[Notif] _resolve_owner fallback failed for {obj}: {e}")

    return None


# --- Main unified signal -------------------------------------------------
@receiver(post_save, sender=Comment, dispatch_uid="notifications.comment.create_v3")
def on_comment_created(sender, instance: Comment, created, **kwargs):
    """
    Handles notifications for both root comments and replies.
    Automatically links to the comment itself (deep-link), 
    falling back to the parent post/testimony if needed.
    """
    if not created:
        return

    actor = getattr(instance, "name", None)  # FK to CustomUser
    if not actor:
        return

    # --- Try resolving main target (post/testimony/whatever) ---
    try:
        target = instance.content_type.get_object_for_this_type(pk=instance.object_id)
    except Exception as e:
        logger.debug(f"[Notif] Failed to resolve target for comment {instance.id}: {e}")
        target = None

    post_owner = _resolve_owner(target)

    # --- Case 1: Root comment on a post/testimony ---
    if instance.recomment is None:
        if post_owner and post_owner.id != actor.id:
            create_and_dispatch_notification(
                recipient=post_owner,
                actor=actor,
                notif_type="new_comment",
                message=f"{actor.username} commented on your post.",
                target_obj=target,
                action_obj=instance,  # 👈 key for deep link
            )
            logger.debug(f"[Notif] new_comment → {post_owner.username} by {actor.username}")

    # --- Case 2: Reply to another comment ---
    else:
        parent = instance.recomment
        original_author = getattr(parent, "name", None)

        # Notify original comment author
        if original_author and original_author.id != actor.id:
            create_and_dispatch_notification(
                recipient=original_author,
                actor=actor,
                notif_type="new_reply",
                message=f"{actor.username} replied to your comment.",
                target_obj=parent,
                action_obj=instance,
            )
            logger.debug(f"[Notif] new_reply → {original_author.username}")

        # Notify post/testimony owner (if distinct)
        try:
            parent_target = parent.content_type.get_object_for_this_type(pk=parent.object_id)
        except Exception:
            parent_target = None

        parent_post_owner = _resolve_owner(parent_target)
        if parent_post_owner and parent_post_owner.id not in (
            actor.id,
            getattr(original_author, "id", None),
        ):
            create_and_dispatch_notification(
                recipient=parent_post_owner,
                actor=actor,
                notif_type="new_reply_post_owner",
                message=f"{actor.username} replied to a comment on your post.",
                target_obj=parent_target,
                action_obj=instance,
            )
            logger.debug(f"[Notif] new_reply_post_owner → {parent_post_owner.username}")

    logger.debug(f"[Notif] Comment signal completed for comment {instance.id}")
