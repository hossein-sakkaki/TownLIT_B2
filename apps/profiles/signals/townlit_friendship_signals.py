# apps/profiles/signals/townlit_friendship_signals.py

from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.profiles.models import Friendship, Member
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation


def _schedule_for_user(user_id: int):
    member = Member.objects.filter(user_id=user_id).only("id").first()
    if not member:
        return
    transaction.on_commit(lambda: trigger_member_townlit_evaluation(member.id))


def _schedule_for_both(instance):
    if instance.from_user_id:
        _schedule_for_user(instance.from_user_id)
    if instance.to_user_id:
        _schedule_for_user(instance.to_user_id)


@receiver(post_save, sender=Friendship)
def townlit_after_friendship_save(sender, instance, **kwargs):
    _schedule_for_both(instance)


@receiver(post_delete, sender=Friendship)
def townlit_after_friendship_delete(sender, instance, **kwargs):
    _schedule_for_both(instance)