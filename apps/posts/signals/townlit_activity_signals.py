# apps/posts/signals/townlit_activity_signals.py

from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.models.testimony import Testimony
from apps.profiles.models import Member
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation


def _resolve_member_from_content_object(obj):
    content_object = getattr(obj, "content_object", None)
    if isinstance(content_object, Member):
        return content_object
    return None


def _schedule(member_id: int):
    transaction.on_commit(lambda: trigger_member_townlit_evaluation(member_id))


def _schedule_from_instance(instance):
    member = _resolve_member_from_content_object(instance)
    if member:
        _schedule(member.id)


@receiver(post_save, sender=Moment)
def townlit_after_moment_save(sender, instance, **kwargs):
    _schedule_from_instance(instance)


@receiver(post_delete, sender=Moment)
def townlit_after_moment_delete(sender, instance, **kwargs):
    _schedule_from_instance(instance)


@receiver(post_save, sender=Prayer)
def townlit_after_prayer_save(sender, instance, **kwargs):
    _schedule_from_instance(instance)


@receiver(post_delete, sender=Prayer)
def townlit_after_prayer_delete(sender, instance, **kwargs):
    _schedule_from_instance(instance)


@receiver(post_save, sender=Testimony)
def townlit_after_testimony_save(sender, instance, **kwargs):
    _schedule_from_instance(instance)


@receiver(post_delete, sender=Testimony)
def townlit_after_testimony_delete(sender, instance, **kwargs):
    _schedule_from_instance(instance)