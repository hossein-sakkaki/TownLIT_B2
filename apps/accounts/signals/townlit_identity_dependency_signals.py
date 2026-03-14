# apps/accounts/signals/townlit_identity_dependency_signals.py

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models.identity import IdentityVerification
from apps.profiles.models import Member
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation


def _schedule(member_id: int):
    transaction.on_commit(lambda: trigger_member_townlit_evaluation(member_id))


@receiver(post_save, sender=IdentityVerification)
def evaluate_townlit_after_identity_change(sender, instance, **kwargs):
    member = Member.objects.filter(user=instance.user).only("id").first()
    if member:
        _schedule(member.id)