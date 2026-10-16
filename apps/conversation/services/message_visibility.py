# apps/conversation/services/message_visibility.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from apps.conversation.models import DialogueParticipant
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.organizations.constants import OrganizationStatus
from apps.organizations.selectors import is_organization_verified


def is_members_community(dialogue) -> bool:
    return (
        ConversationContextPolicy.resolve(dialogue).kind
        == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
    )


def user_can_view_message(*, message, user) -> bool:
    dialogue = message.dialogue
    access = ConversationAccessPolicy.can_view(
        dialogue=dialogue,
        user=user,
    )
    if not access.allowed:
        return False

    return (
        dialogue.visible_messages_for_user(user)
        .filter(id=message.id)
        .exists()
    )


def visible_participant_ids_for_message(*, message) -> list[int]:
    dialogue = message.dialogue
    context = ConversationContextPolicy.resolve(dialogue)

    if (
        context.kind
        != ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
    ):
        return list(
            dialogue.participants.values_list("id", flat=True)
        )

    organization = context.organization_context.organization
    if (
        organization.status != OrganizationStatus.ACTIVE
        or not is_organization_verified(organization=organization)
    ):
        return []

    current_user_ids = dialogue.participants.values_list("id", flat=True)
    return list(
        DialogueParticipant.objects
        .filter(
            dialogue=dialogue,
            user_id__in=current_user_ids,
            joined_at__lte=message.timestamp,
        )
        .values_list("user_id", flat=True)
    )


def visible_message_ids_for_user(*, dialogue, user, message_ids) -> list[int]:
    normalized_ids = [
        int(message_id)
        for message_id in (message_ids or [])
        if message_id
    ]
    if not normalized_ids:
        return []

    access = ConversationAccessPolicy.can_view(
        dialogue=dialogue,
        user=user,
    )
    if not access.allowed:
        return []

    return list(
        dialogue.visible_messages_for_user(user)
        .filter(id__in=normalized_ids)
        .values_list("id", flat=True)
    )
