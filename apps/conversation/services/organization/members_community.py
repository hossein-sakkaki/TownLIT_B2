# apps/conversation/services/organization/members_community.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
    OrganizationConversationWaitingFor,
)
from apps.conversation.models import (
    Dialogue,
    OrganizationDialogueContext,
)
from apps.organizations.models import Organization
from apps.organizations.services.roles import bootstrap_organization_access

from .availability import organization_messenger_is_available
from .membership_sync import reconcile_all_members_community_memberships


@dataclass(frozen=True)
class MembersCommunityReconciliationResult:
    context: OrganizationDialogueContext | None
    available: bool
    created: bool = False
    added_count: int = 0
    removed_count: int = 0
    updated_count: int = 0
    member_count: int = 0


def members_community_fallback_name(organization) -> str:
    name = " ".join(str(getattr(organization, "name", "") or "").split())
    return f"{name or 'Organization'} · Members"


def get_members_community_context(*, organization):
    return (
        OrganizationDialogueContext.objects
        .select_related(
            "dialogue",
            "organization",
        )
        .filter(
            organization=organization,
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
        )
        .first()
    )


def _sync_fallback_metadata(*, context) -> None:
    dialogue = context.dialogue
    expected_name = members_community_fallback_name(context.organization)

    if dialogue.group_name == expected_name:
        return

    dialogue.group_name = expected_name
    dialogue.save(update_fields=["group_name"])


def _create_members_community(*, organization):
    fallback_name = members_community_fallback_name(organization)
    dialogue = Dialogue.objects.create(
        is_group=True,
        group_name=fallback_name,
        rsa_required=False,
        slug=Dialogue.generate_dialogue_slug(
            [],
            fallback_name,
        ),
    )

    context = OrganizationDialogueContext(
        dialogue=dialogue,
        organization=organization,
        context_type=OrganizationConversationContextType.MEMBERS_COMMUNITY,
        status=OrganizationConversationStatus.OPEN,
        waiting_for=OrganizationConversationWaitingFor.NONE,
    )
    context.full_clean()
    context.save()
    return context


@transaction.atomic
def reconcile_organization_members_community(
    *,
    organization,
    emit_visibility_event=False,
):
    """
    Reconcile one Organization's canonical Members Community.

    Verification/lifecycle suspension removes runtime access but preserves the
    Dialogue and active-membership history boundaries. Membership ineligibility
    removes the history boundary so a later rejoin starts a new window.
    """
    locked_organization = (
        Organization.objects
        .select_for_update()
        .get(pk=organization.pk)
    )

    context = get_members_community_context(
        organization=locked_organization,
    )
    if context:
        _sync_fallback_metadata(context=context)

    available = organization_messenger_is_available(locked_organization)
    if not available and context is None:
        return MembersCommunityReconciliationResult(
            context=None,
            available=False,
        )

    created = False
    if available:
        # Existing Organizations need the current Messenger permission catalog.
        bootstrap_organization_access(locked_organization)

        if context is None:
            context = _create_members_community(
                organization=locked_organization,
            )
            created = True

    membership_result = reconcile_all_members_community_memberships(
        context=context,
        available=available,
        emit_events=bool(emit_visibility_event),
    )

    return MembersCommunityReconciliationResult(
        context=context,
        available=available,
        created=created,
        **membership_result,
    )
