# apps/profiles/signals/townlit_member_m2m_signals.py

from django.db import transaction
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from apps.profiles.models import Member
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation


def _schedule(member_id: int):
    transaction.on_commit(lambda: trigger_member_townlit_evaluation(member_id))


@receiver(m2m_changed, sender=Member.service_types.through)
def evaluate_townlit_after_service_types_change(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        _schedule(instance.id)


@receiver(m2m_changed, sender=Member.organization_memberships.through)
def evaluate_townlit_after_organization_memberships_change(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        _schedule(instance.id)