# apps/profiles/signals/townlit_member_m2m_signals.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-13.
# Last Update by Hossein Sakkaki on 2026-09-13.
#

from django.db import transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
)
from django.dispatch import receiver

from apps.accounts.services.townlit_trigger import (
    trigger_member_townlit_evaluation,
)
from apps.organizations.models import (
    OrganizationMembership,
)
from apps.profiles.models import Member


def _schedule(member_id: int):
    transaction.on_commit(
        lambda: trigger_member_townlit_evaluation(
            member_id
        )
    )


@receiver(
    m2m_changed,
    sender=Member.service_types.through,
)
def evaluate_townlit_after_service_types_change(
    sender,
    instance,
    action,
    **kwargs,
):
    if action in {
        "post_add",
        "post_remove",
        "post_clear",
    }:
        _schedule(instance.id)


@receiver(
    post_save,
    sender=OrganizationMembership,
)
def evaluate_townlit_after_organization_membership_save(
    sender,
    instance,
    **kwargs,
):
    if instance.member_id:
        _schedule(instance.member_id)


@receiver(
    post_delete,
    sender=OrganizationMembership,
)
def evaluate_townlit_after_organization_membership_delete(
    sender,
    instance,
    **kwargs,
):
    if instance.member_id:
        _schedule(instance.member_id)