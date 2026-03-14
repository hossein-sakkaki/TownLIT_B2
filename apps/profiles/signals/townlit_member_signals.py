# apps/profiles/signals/townlit_member_signals.py

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profiles.models import Member
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation


TOWNLIT_RELATED_MEMBER_FIELDS = {
    "biography",
    "vision",
    "spiritual_rebirth_day",
    "denomination_branch",
}


def _schedule(member_id: int):
    transaction.on_commit(lambda: trigger_member_townlit_evaluation(member_id))


@receiver(post_save, sender=Member)
def evaluate_townlit_after_member_save(sender, instance, created, update_fields=None, **kwargs):
    if created:
        _schedule(instance.id)
        return

    if update_fields is None:
        _schedule(instance.id)
        return

    if TOWNLIT_RELATED_MEMBER_FIELDS.intersection(set(update_fields)):
        _schedule(instance.id)