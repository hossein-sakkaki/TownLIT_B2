# apps/profiles/signals/trust_friendship_signals.py

from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.profiles.models import Friendship
from apps.accounts.services.trust_engine import trigger_trust_recalculation


def _schedule_trust_recalculation(user_id: int):
    """
    Delay trust recalculation until transaction commit.
    """
    transaction.on_commit(lambda: trigger_trust_recalculation(user_id))


def _schedule_for_both_users(instance):
    """
    Recalculate trust for both sides of the friendship.
    """
    if instance.from_user_id:
        _schedule_trust_recalculation(instance.from_user_id)

    if instance.to_user_id:
        _schedule_trust_recalculation(instance.to_user_id)


@receiver(post_save, sender=Friendship)
def trust_after_friendship_save(sender, instance, **kwargs):
    """
    Recalculate trust after friendship save.
    Covers:
    - pending creation
    - accepted transition
    - soft delete / inactive transition
    """
    _schedule_for_both_users(instance)


@receiver(post_delete, sender=Friendship)
def trust_after_friendship_delete(sender, instance, **kwargs):
    """
    Recalculate trust after friendship hard delete.
    """
    _schedule_for_both_users(instance)