# apps/conversation/services/boundary_access.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from apps.core.boundaries.constants import BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE
from apps.core.boundaries.services.policy import BoundaryPolicy


CONVERSATION_INTERACTION_UNAVAILABLE_CODE = "interaction_unavailable"
GROUP_BOUNDARY_CONFLICT_CODE = "group_boundary_conflict"


@dataclass(frozen=True)
class ConversationBoundaryCheck:
    allowed: bool
    message: str = ""
    code: str = ""
    counterpart_id: int | None = None


def conversation_boundary_error_payload(
    *,
    message: str = BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
    code: str = CONVERSATION_INTERACTION_UNAVAILABLE_CODE,
) -> dict:
    return {
        "error": message,
        "code": code,
    }


def private_dialogue_counterpart(dialogue, acting_user):
    """
    Return the other participant for a private dialogue.
    Returns None for group dialogues or malformed private dialogues.
    """
    if not dialogue or getattr(dialogue, "is_group", False):
        return None

    return dialogue.participants.exclude(id=acting_user.id).first()


def check_private_dialogue_boundary(*, dialogue, acting_user) -> ConversationBoundaryCheck:
    """
    Direct private messaging is unavailable when Boundary exists
    in either direction between the two private participants.

    Existing private history remains readable.
    New direct interaction is blocked.
    """
    if not dialogue or getattr(dialogue, "is_group", False):
        return ConversationBoundaryCheck(allowed=True)

    counterpart = private_dialogue_counterpart(dialogue, acting_user)

    if not counterpart:
        return ConversationBoundaryCheck(allowed=True)

    if BoundaryPolicy.has_boundary_between(acting_user, counterpart):
        return ConversationBoundaryCheck(
            allowed=False,
            message=BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
            code=CONVERSATION_INTERACTION_UNAVAILABLE_CODE,
            counterpart_id=counterpart.id,
        )

    return ConversationBoundaryCheck(allowed=True, counterpart_id=counterpart.id)


def private_dialogue_boundary_response_payload(*, dialogue, acting_user) -> Optional[dict]:
    check = check_private_dialogue_boundary(
        dialogue=dialogue,
        acting_user=acting_user,
    )

    if check.allowed:
        return None

    return conversation_boundary_error_payload(
        message=check.message,
        code=check.code,
    )


def can_create_private_dialogue(*, acting_user, recipient) -> ConversationBoundaryCheck:
    """
    Creating/opening a private dialogue for direct interaction is blocked
    when Boundary exists in either direction.
    """
    if BoundaryPolicy.has_boundary_between(acting_user, recipient):
        return ConversationBoundaryCheck(
            allowed=False,
            message=BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
            code=CONVERSATION_INTERACTION_UNAVAILABLE_CODE,
            counterpart_id=recipient.id,
        )

    return ConversationBoundaryCheck(allowed=True, counterpart_id=recipient.id)


def group_boundary_conflict_for_add(*, dialogue, target_user):
    """
    New group additions should not force two users with an active Boundary
    into a new private group space.

    Existing shared groups are preserved.
    Future additions are blocked if target_user has Boundary with any
    existing participant.
    """
    if not dialogue or not getattr(dialogue, "is_group", False):
        return None

    existing_participants = (
        dialogue.participants
        .exclude(id=target_user.id)
        .only("id", "username", "email")
    )

    for participant in existing_participants:
        if BoundaryPolicy.has_boundary_between(participant, target_user):
            return participant

    return None


def can_add_user_to_group(*, dialogue, target_user) -> ConversationBoundaryCheck:
    conflict_user = group_boundary_conflict_for_add(
        dialogue=dialogue,
        target_user=target_user,
    )

    if conflict_user:
        return ConversationBoundaryCheck(
            allowed=False,
            message="This person cannot be added to this group right now.",
            code=GROUP_BOUNDARY_CONFLICT_CODE,
            counterpart_id=conflict_user.id,
        )

    return ConversationBoundaryCheck(allowed=True)


def should_send_conversation_notification(*, actor, recipient) -> bool:
    """
    Used by group unread/realtime notification paths.

    Stillness:
        recipient placed actor in Stillness -> no interruption.

    Boundary:
        either direction -> no interruption.

    The actual group message can still be visible in the group.
    """
    if not actor or not recipient:
        return True

    if getattr(actor, "id", None) == getattr(recipient, "id", None):
        return False

    return BoundaryPolicy.can_notify(
        actor=actor,
        recipient=recipient,
    )