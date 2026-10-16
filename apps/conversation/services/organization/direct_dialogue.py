# apps/conversation/services/organization/direct_dialogue.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
    OrganizationConversationWaitingFor,
)
from apps.conversation.models import Dialogue, OrganizationDialogueContext

from .availability import organization_messenger_is_available


@dataclass(frozen=True)
class OrganizationDirectContextResult:
    ok: bool
    context: OrganizationDialogueContext | None = None
    created: bool = False
    code: str = ""
    message: str = ""
    status: int = 200


def get_organization_direct_context(*, organization, participant_user):
    return (
        OrganizationDialogueContext.objects
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
            "assigned_to_membership__member__user",
        )
        .filter(
            organization=organization,
            context_type=OrganizationConversationContextType.DIRECT,
            participant_user=participant_user,
        )
        .first()
    )


def get_organization_direct_context_by_slug(*, organization, dialogue_slug):
    return (
        OrganizationDialogueContext.objects
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
            "assigned_to_membership__member__user",
        )
        .filter(
            organization=organization,
            context_type=OrganizationConversationContextType.DIRECT,
            dialogue__slug=dialogue_slug,
        )
        .first()
    )


@transaction.atomic
def ensure_organization_direct_context(*, organization, participant_user):
    """Return the lifetime canonical Organization×User direct Dialogue."""
    existing = get_organization_direct_context(
        organization=organization,
        participant_user=participant_user,
    )
    if existing is not None:
        return OrganizationDirectContextResult(
            ok=True,
            context=existing,
            created=False,
        )

    if not organization_messenger_is_available(organization):
        return OrganizationDirectContextResult(
            ok=False,
            code="organization_messenger_unavailable",
            message="Organization Messenger is not currently available.",
            status=403,
        )

    try:
        # The DB uniqueness constraint is the concurrency authority.
        # A savepoint lets a racing request recover the canonical row
        # without serializing every new conversation on Organization.
        with transaction.atomic():
            dialogue = Dialogue.objects.create(
                is_group=False,
                rsa_required=False,
                slug=Dialogue.generate_dialogue_slug([]),
            )
            dialogue.participants.add(participant_user)

            context = OrganizationDialogueContext(
                dialogue=dialogue,
                organization=organization,
                context_type=OrganizationConversationContextType.DIRECT,
                participant_user=participant_user,
                status=OrganizationConversationStatus.OPEN,
                waiting_for=OrganizationConversationWaitingFor.ORGANIZATION,
            )
            context.full_clean(
                validate_unique=False,
                validate_constraints=False,
            )
            context.save()
    except IntegrityError:
        existing = get_organization_direct_context(
            organization=organization,
            participant_user=participant_user,
        )
        if existing is None:
            raise
        return OrganizationDirectContextResult(
            ok=True,
            context=existing,
            created=False,
        )

    return OrganizationDirectContextResult(
        ok=True,
        context=context,
        created=True,
        status=201,
    )
