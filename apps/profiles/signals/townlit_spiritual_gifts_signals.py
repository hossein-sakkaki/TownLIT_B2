# apps/profiles/signals/townlit_spiritual_gifts_signals.py

from django.db import transaction
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from apps.profiles.models import MemberSpiritualGifts
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation


def _schedule(member_id: int):
    transaction.on_commit(lambda: trigger_member_townlit_evaluation(member_id))


@receiver(post_save, sender=MemberSpiritualGifts)
def evaluate_townlit_after_spiritual_gifts_save(sender, instance, **kwargs):
    if instance.member_id:
        _schedule(instance.member_id)


@receiver(post_delete, sender=MemberSpiritualGifts)
def evaluate_townlit_after_spiritual_gifts_delete(sender, instance, **kwargs):
    if instance.member_id:
        _schedule(instance.member_id)


@receiver(m2m_changed, sender=MemberSpiritualGifts.gifts.through)
def evaluate_townlit_after_spiritual_gifts_m2m_change(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"} and instance.member_id:
        _schedule(instance.member_id)