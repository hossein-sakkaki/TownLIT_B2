# apps/motivations/signals/common_signals.py

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.notifications.models import Notification
from apps.posts.models.testimony import Testimony
from apps.posts.models.reaction import Reaction
from apps.posts.models.comment import Comment
from apps.profiles.models import Friendship, Fellowship


# ---------------------------------------------------------
# SAFE helper: delete notifications for a given instance
# ---------------------------------------------------------
def delete_notifications_for_instance(instance):
    """
    Safely delete Notification rows for an instance.
    Supports both:
      - target_content_type / target_object_id
      - action_content_type / action_object_id
    No errors if CT or fields do not exist.
    """

    try:
        ct = ContentType.objects.get_for_model(instance.__class__)
    except Exception:
        return  # CT lookup failed → ignore

    oid = instance.pk
    if not oid:
        return

    # Build a Q expression that covers both possible foreign key pairs
    q = (
        models.Q(target_content_type=ct, target_object_id=oid) |
        models.Q(action_content_type=ct, action_object_id=oid)
    )

    try:
        Notification.objects.filter(q).delete()
    except Exception:
        # Never break delete operations due to Notification cleanup
        pass


# ---------------------------------------------------------
# SAFE helper: delete notifications for children (comments/reactions)
# ---------------------------------------------------------
def delete_notifications_for_children_comments_and_reactions(parent_instance):
    """
    Safely delete notifications for Comment/Reaction children.
    """

    try:
        parent_ct = ContentType.objects.get_for_model(parent_instance.__class__)
    except Exception:
        return

    pid = parent_instance.pk
    if not pid:
        return

    # Get all comment IDs attached to this parent
    try:
        comment_ids = list(
            Comment.objects.filter(
                content_type=parent_ct,
                object_id=pid
            ).values_list("id", flat=True)
        )
    except Exception:
        comment_ids = []

    # Get all reaction IDs attached to this parent
    try:
        reaction_ids = list(
            Reaction.objects.filter(
                content_type=parent_ct,
                object_id=pid
            ).values_list("id", flat=True)
        )
    except Exception:
        reaction_ids = []

    # Clean comment notifications
    if comment_ids:
        try:
            c_ct = ContentType.objects.get_for_model(Comment)
            Notification.objects.filter(
                models.Q(target_content_type=c_ct, target_object_id__in=comment_ids) |
                models.Q(action_content_type=c_ct, action_object_id__in=comment_ids)
            ).delete()
        except Exception:
            pass

    # Clean reaction notifications
    if reaction_ids:
        try:
            r_ct = ContentType.objects.get_for_model(Reaction)
            Notification.objects.filter(
                models.Q(target_content_type=r_ct, target_object_id__in=reaction_ids) |
                models.Q(action_content_type=r_ct, action_object_id__in=reaction_ids)
            ).delete()
        except Exception:
            pass


# ---------------------------------------------------------
# Visibility helper
# ---------------------------------------------------------
def is_content_unavailable(obj) -> bool:
    """Determine whether content should be hidden from users."""
    return (
        getattr(obj, "is_active", True) is False
        or getattr(obj, "is_hidden", False) is True
        or getattr(obj, "is_suspended", False) is True
        or getattr(obj, "is_restricted", False) is True
    )


# =========================================================
# SIGNALS — SAFE, FUTURE-PROOF
# =========================================================


@receiver(post_delete, sender=Testimony)
def cleanup_notifications_on_testimony_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)
    delete_notifications_for_children_comments_and_reactions(instance)


@receiver(post_save, sender=Testimony)
def cleanup_notifications_on_testimony_visibility(sender, instance, **kwargs):
    if is_content_unavailable(instance):
        delete_notifications_for_instance(instance)
        delete_notifications_for_children_comments_and_reactions(instance)


@receiver(post_delete, sender=Comment)
def cleanup_notifications_on_comment_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)


@receiver(post_delete, sender=Reaction)
def cleanup_notifications_on_reaction_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)


@receiver(post_delete, sender=Friendship)
@receiver(post_delete, sender=Fellowship)
def cleanup_notifications_on_relationship_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)
