# apps/conversation/policies/history.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from enum import Enum

from apps.conversation.models import DialogueParticipant

from .context import ConversationContextKind, ConversationContextPolicy


class ConversationHistoryMode(str, Enum):
    EXISTING_VISIBILITY = "existing_visibility"
    FROM_CURRENT_PARTICIPATION = "from_current_participation"


class ConversationHistoryPolicy:
    """Apply context-specific history boundaries to existing visibility."""

    @classmethod
    def mode(cls, dialogue) -> ConversationHistoryMode:
        context = ConversationContextPolicy.resolve(dialogue)
        if (
            context.kind
            == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY
        ):
            return ConversationHistoryMode.FROM_CURRENT_PARTICIPATION
        return ConversationHistoryMode.EXISTING_VISIBILITY

    @classmethod
    def current_history_start(cls, *, dialogue, user):
        if cls.mode(dialogue) != ConversationHistoryMode.FROM_CURRENT_PARTICIPATION:
            return None

        participant = (
            DialogueParticipant.objects
            .filter(
                dialogue=dialogue,
                user=user,
            )
            .only("joined_at")
            .first()
        )
        return participant.joined_at if participant else None

    @classmethod
    def apply_visibility_boundary(
        cls,
        *,
        dialogue,
        user,
        queryset,
    ):
        if cls.mode(dialogue) != ConversationHistoryMode.FROM_CURRENT_PARTICIPATION:
            return queryset

        if not dialogue.participants.filter(id=user.id).exists():
            return queryset.none()

        history_start = cls.current_history_start(
            dialogue=dialogue,
            user=user,
        )
        if history_start is None:
            return queryset.none()

        return queryset.filter(
            timestamp__gte=history_start,
        )
