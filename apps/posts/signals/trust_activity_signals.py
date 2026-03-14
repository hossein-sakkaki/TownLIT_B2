# apps/posts/signals/trust_activity_signals.py

from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.models.testimony import Testimony
from apps.accounts.services.trust_engine import trigger_trust_recalculation

from apps.profiles.models import Member, GuestUser


def _resolve_user_from_content_object(obj):
    """
    Resolve CustomUser from polymorphic content owner.
    """
    content_object = getattr(obj, "content_object", None)
    if not content_object:
        return None

    if isinstance(content_object, Member):
        return getattr(content_object, "user", None)

    if isinstance(content_object, GuestUser):
        return getattr(content_object, "user", None)

    return None


def _schedule_trust_recalculation(user_id: int):
    """
    Delay trust recalculation until transaction commit.
    """
    transaction.on_commit(lambda: trigger_trust_recalculation(user_id))


def _recalculate_from_instance(instance):
    """
    Shared helper for create/delete trust refresh.
    """
    user = _resolve_user_from_content_object(instance)
    if user:
        _schedule_trust_recalculation(user.id)


@receiver(post_save, sender=Moment)
def trust_after_moment_save(sender, instance, created, **kwargs):
    """
    Recalculate trust after moment creation.
    """
    if not created:
        return
    _recalculate_from_instance(instance)


@receiver(post_delete, sender=Moment)
def trust_after_moment_delete(sender, instance, **kwargs):
    """
    Recalculate trust after moment deletion.
    """
    _recalculate_from_instance(instance)


@receiver(post_save, sender=Prayer)
def trust_after_prayer_save(sender, instance, created, **kwargs):
    """
    Recalculate trust after prayer creation.
    """
    if not created:
        return
    _recalculate_from_instance(instance)


@receiver(post_delete, sender=Prayer)
def trust_after_prayer_delete(sender, instance, **kwargs):
    """
    Recalculate trust after prayer deletion.
    """
    _recalculate_from_instance(instance)


@receiver(post_save, sender=Testimony)
def trust_after_testimony_save(sender, instance, created, **kwargs):
    """
    Recalculate trust after testimony creation.
    """
    if not created:
        return   
    _recalculate_from_instance(instance)


@receiver(post_delete, sender=Testimony)
def trust_after_testimony_delete(sender, instance, **kwargs):
    """
    Recalculate trust after testimony deletion.
    """
    _recalculate_from_instance(instance)