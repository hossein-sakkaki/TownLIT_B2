# apps/conversation/policies/audience.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from apps.organizations.constants import OrganizationPermissionKey

from .context import ConversationContextKind, ConversationContextPolicy


class ConversationAudienceKind(str, Enum):
    OTHER_DIALOGUE_PARTICIPANTS = "other_dialogue_participants"
    ORGANIZATION_OPERATORS = "organization_operators"
    ORGANIZATION_DIRECT_PARTICIPANT = "organization_direct_participant"
    NONE = "none"


@dataclass(frozen=True)
class ConversationAudienceDecision:
    kind: ConversationAudienceKind
    organization_id: int | None = None
    participant_user_id: int | None = None
    required_permission_key: str | None = None


class ConversationAudiencePolicy:
    """Describe authoritative fan-out strategy without dispatching events."""

    @classmethod
    def for_message(
        cls,
        *,
        dialogue,
        actor,
        sent_as_organization: bool = False,
    ) -> ConversationAudienceDecision:
        context = ConversationContextPolicy.resolve(dialogue)

        if context.kind in {
            ConversationContextKind.PERSONAL_DIRECT,
            ConversationContextKind.PERSONAL_GROUP,
            ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY,
        }:
            return ConversationAudienceDecision(
                kind=ConversationAudienceKind.OTHER_DIALOGUE_PARTICIPANTS,
            )

        organization_context = context.organization_context

        if sent_as_organization:
            return ConversationAudienceDecision(
                kind=(
                    ConversationAudienceKind.ORGANIZATION_DIRECT_PARTICIPANT
                ),
                organization_id=organization_context.organization_id,
                participant_user_id=(
                    organization_context.participant_user_id
                ),
            )

        if (
            actor
            and getattr(actor, "id", None)
            == organization_context.participant_user_id
        ):
            return ConversationAudienceDecision(
                kind=ConversationAudienceKind.ORGANIZATION_OPERATORS,
                organization_id=organization_context.organization_id,
                required_permission_key=(
                    OrganizationPermissionKey.VIEW_MESSENGER
                ),
            )

        return ConversationAudienceDecision(
            kind=ConversationAudienceKind.NONE,
            organization_id=organization_context.organization_id,
        )
