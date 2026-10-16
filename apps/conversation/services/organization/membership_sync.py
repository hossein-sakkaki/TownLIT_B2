# apps/conversation/services/organization/membership_sync.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.conversation.constants import (
    PARTICIPANT,
    OrganizationConversationContextType,
)
from apps.conversation.models import (
    DialogueParticipant,
    DialoguePin,
    OrganizationDialogueContext,
    UserDialogueMarker,
)
from apps.conversation.services.event_contracts import (
    build_group_added_event_data,
    build_group_removed_event_data,
)
from apps.conversation.services.realtime_dispatch import (
    conv_group_send,
    conversation_user_group_name,
)
from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
)
from apps.organizations.models import OrganizationMembership

from .availability import organization_messenger_is_available


User = get_user_model()


@dataclass(frozen=True)
class CommunityMembershipSyncResult:
    added: bool = False
    removed: bool = False
    participant_created: bool = False
    participant_removed: bool = False
    role_updated: bool = False


def _community_context_for_organization(organization_id):
    return (
        OrganizationDialogueContext.objects
        .select_related(
            "dialogue",
            "organization",
        )
        .filter(
            organization_id=organization_id,
            context_type=(
                OrganizationConversationContextType.MEMBERS_COMMUNITY
            ),
        )
        .first()
    )


def _dialogue_realtime_payload(dialogue):
    # Local import avoids a serializer/service import cycle at module load.
    from apps.conversation.serializers import DialogueSerializer

    return DialogueSerializer(
        dialogue,
        context={},
    ).data


def _dispatch_membership_event_after_commit(*, dialogue, user_id, added):
    def _dispatch():
        payload = _dialogue_realtime_payload(dialogue)
        event_data = (
            build_group_added_event_data(dialogue=payload)
            if added
            else build_group_removed_event_data(dialogue=payload)
        )
        conv_group_send(
            conversation_user_group_name(user_id),
            "group_added" if added else "group_removed",
            event_data,
        )

    transaction.on_commit(_dispatch)


def _ensure_history_participant(*, dialogue, membership):
    """Ensure the current official membership has one history boundary row."""
    user = membership.member.user
    participant, created = DialogueParticipant.objects.get_or_create(
        dialogue=dialogue,
        user=user,
        defaults={
            "role": PARTICIPANT,
        },
    )

    role_updated = False
    if participant.role != PARTICIPANT:
        participant.role = PARTICIPANT
        participant.save(update_fields=["role"])
        role_updated = True

    return participant, created, role_updated


def _grant_runtime_access(*, dialogue, user, emit_event=True) -> bool:
    """Grant current Community access without changing the history boundary."""
    already_allowed = dialogue.participants.filter(id=user.id).exists()
    if already_allowed:
        return False

    dialogue.participants.add(user)
    dialogue.deleted_by_users.remove(user)

    if emit_event:
        _dispatch_membership_event_after_commit(
            dialogue=dialogue,
            user_id=user.id,
            added=True,
        )
    return True


def _suspend_runtime_access(*, dialogue, user, emit_event=True) -> bool:
    """Suspend Community access while preserving current membership history."""
    had_access = dialogue.participants.filter(id=user.id).exists()
    if not had_access:
        return False

    dialogue.participants.remove(user)

    if emit_event:
        _dispatch_membership_event_after_commit(
            dialogue=dialogue,
            user_id=user.id,
            added=False,
        )
    return True


def _remove_membership_state(*, dialogue, user, emit_event=True):
    """Remove Community access and reset history after membership eligibility ends."""
    had_access = dialogue.participants.filter(id=user.id).exists()

    if had_access:
        dialogue.participants.remove(user)

    participant_removed, _ = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=user,
    ).delete()

    # User-scoped state must not resurrect an old membership history window.
    DialoguePin.objects.filter(
        dialogue=dialogue,
        user=user,
    ).delete()
    UserDialogueMarker.objects.filter(
        dialogue=dialogue,
        user=user,
    ).delete()
    dialogue.deleted_by_users.remove(user)

    if had_access and emit_event:
        _dispatch_membership_event_after_commit(
            dialogue=dialogue,
            user_id=user.id,
            added=False,
        )

    return CommunityMembershipSyncResult(
        removed=had_access,
        participant_removed=bool(participant_removed),
    )


def _reconcile_eligible_membership(
    *,
    dialogue,
    membership,
    available,
    emit_event=True,
):
    user = membership.member.user
    _participant, created, role_updated = _ensure_history_participant(
        dialogue=dialogue,
        membership=membership,
    )

    if available:
        added = _grant_runtime_access(
            dialogue=dialogue,
            user=user,
            emit_event=emit_event,
        )
        return CommunityMembershipSyncResult(
            added=added,
            participant_created=created,
            role_updated=role_updated,
        )

    removed = _suspend_runtime_access(
        dialogue=dialogue,
        user=user,
        emit_event=emit_event,
    )
    return CommunityMembershipSyncResult(
        removed=removed,
        participant_created=created,
        role_updated=role_updated,
    )


@transaction.atomic
def reconcile_organization_user_membership(*, organization_id, user_id):
    """Synchronize one user from authoritative OrganizationMembership state."""
    context = _community_context_for_organization(organization_id)
    if not context:
        return CommunityMembershipSyncResult()

    dialogue = context.dialogue
    membership = (
        OrganizationMembership.objects
        .select_related(
            "member__user",
            "organization",
        )
        .filter(
            organization_id=organization_id,
            member__user_id=user_id,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        )
        .order_by("-joined_at", "-id")
        .first()
    )

    if membership:
        return _reconcile_eligible_membership(
            dialogue=dialogue,
            membership=membership,
            available=organization_messenger_is_available(
                context.organization
            ),
        )

    user = User.objects.filter(pk=user_id).first()
    if not user:
        return CommunityMembershipSyncResult()

    return _remove_membership_state(
        dialogue=dialogue,
        user=user,
    )


@transaction.atomic
def reconcile_all_members_community_memberships(
    *,
    context,
    available=None,
    emit_events=True,
):
    """Reconcile history markers and runtime access for the whole Community."""
    dialogue = context.dialogue
    organization = context.organization

    if available is None:
        available = organization_messenger_is_available(organization)

    memberships = list(
        OrganizationMembership.objects
        .select_related(
            "member__user",
        )
        .filter(
            organization=organization,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        )
        .order_by("joined_at", "id")
    )

    expected_user_ids = {
        membership.member.user_id
        for membership in memberships
    }

    added_count = 0
    removed_count = 0
    updated_count = 0

    for membership in memberships:
        result = _reconcile_eligible_membership(
            dialogue=dialogue,
            membership=membership,
            available=available,
            emit_event=emit_events,
        )
        added_count += int(result.added)
        removed_count += int(result.removed)
        updated_count += int(
            result.participant_created or result.role_updated
        )

    stale_user_ids = set(
        DialogueParticipant.objects
        .filter(dialogue=dialogue)
        .exclude(user_id__in=expected_user_ids)
        .values_list("user_id", flat=True)
    )
    stale_user_ids.update(
        dialogue.participants
        .exclude(id__in=expected_user_ids)
        .values_list("id", flat=True)
    )

    for user in User.objects.filter(id__in=stale_user_ids):
        result = _remove_membership_state(
            dialogue=dialogue,
            user=user,
            emit_event=emit_events,
        )
        removed_count += int(result.removed)
        updated_count += int(result.participant_removed)

    return {
        "added_count": added_count,
        "removed_count": removed_count,
        "updated_count": updated_count,
        "member_count": len(expected_user_ids),
    }
