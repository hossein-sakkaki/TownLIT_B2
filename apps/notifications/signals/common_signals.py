# apps/motivations/signals/common_signals.py


# apps/motivations/signals/common_signals.py

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.notifications.models import Notification  
from apps.posts.models import Comment, Reaction, Testimony  
from apps.profiles.models import Friendship, Fellowship 


# ---------------------------------------------------------
# Helper: delete all notifications for a single instance
# ---------------------------------------------------------
def delete_notifications_for_instance(instance):
    """
    Delete all Notification rows where target = this instance
    (GenericForeignKey via content_type + object_id).
    """
    model = instance.__class__
    ct = ContentType.objects.get_for_model(model)

    Notification.objects.filter(
        content_type=ct,
        object_id=instance.pk,
    ).delete()


# ---------------------------------------------------------
# Helper: delete notifications for children (Comment/Reaction)
# of a given parent object (e.g. Testimony)
# ---------------------------------------------------------
def delete_notifications_for_children_comments_and_reactions(parent_instance):
    """
    For a given parent content (e.g. Testimony), delete all notifications
    that are attached to its Comment and Reaction children.
    """
    parent_ct = ContentType.objects.get_for_model(parent_instance.__class__)

    # All comments directly attached to this parent
    comment_ids = Comment.objects.filter(
        content_type=parent_ct,
        object_id=parent_instance.pk,
    ).values_list("id", flat=True)

    # All reactions directly attached to this parent
    reaction_ids = Reaction.objects.filter(
        content_type=parent_ct,
        object_id=parent_instance.pk,
    ).values_list("id", flat=True)

    if comment_ids:
        comment_ct = ContentType.objects.get_for_model(Comment)
        Notification.objects.filter(
            content_type=comment_ct,
            object_id__in=list(comment_ids),
        ).delete()

    if reaction_ids:
        reaction_ct = ContentType.objects.get_for_model(Reaction)
        Notification.objects.filter(
            content_type=reaction_ct,
            object_id__in=list(reaction_ids),
        ).delete()


# ---------------------------------------------------------
# Helper: decide if a content is "not visible" for users
# ---------------------------------------------------------
def is_content_unavailable(obj) -> bool:
    """
    Central place to define when a piece of content is effectively
    unavailable for normal users.

    You can tweak this logic later if, for example, 'is_restricted'
    should NOT remove notifications.
    """
    return (
        getattr(obj, "is_active", True) is False
        or getattr(obj, "is_hidden", False) is True
        or getattr(obj, "is_suspended", False) is True
        or getattr(obj, "is_restricted", False) is True
    )


# =========================================================
#   SIGNALS
# =========================================================

# 1) HARD DELETE: Testimony deleted → remove all its notifications
#    and notifications for its comments / reactions
@receiver(post_delete, sender=Testimony)
def cleanup_notifications_on_testimony_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)
    delete_notifications_for_children_comments_and_reactions(instance)


# 2) MODERATION / SOFT VISIBILITY CHANGE:
#    whenever Testimony is saved and is effectively unavailable,
#    remove its notifications and notifications of its children.
@receiver(post_save, sender=Testimony)
def cleanup_notifications_on_testimony_visibility(sender, instance, **kwargs):
    """
    If a Testimony becomes unavailable (is_active=False, hidden, suspended,
    restricted), clean up related notifications so users won't click on a
    dead target and get an error.
    """
    if is_content_unavailable(instance):
        delete_notifications_for_instance(instance)
        delete_notifications_for_children_comments_and_reactions(instance)


# 3) When a Comment is deleted → delete its notifications
@receiver(post_delete, sender=Comment)
def cleanup_notifications_on_comment_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)


# 4) When a Reaction is deleted → delete its notifications
@receiver(post_delete, sender=Reaction)
def cleanup_notifications_on_reaction_delete(sender, instance, **kwargs):
    delete_notifications_for_instance(instance)


# 5) When a Friendship or Fellowship is deleted → delete their notifications
@receiver(post_delete, sender=Friendship)
@receiver(post_delete, sender=Fellowship)
def cleanup_notifications_on_relationship_delete(sender, instance, **kwargs):
    """
    Any notification whose target is this Friendship/Fellowship
    should be removed as well.
    """
    delete_notifications_for_instance(instance)
