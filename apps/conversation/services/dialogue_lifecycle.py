# apps/conversation/services/dialogue_lifecycle.py

from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.conversation.models import Dialogue, DialogueParticipant, Message
from validators.groupNames.group_name_validator import validate_group_name

from apps.conversation.services.boundary_access import (
    can_create_private_dialogue,
)


def _error(code: str, message: str, status_code: int):
    """Build a stable service error payload."""
    return {
        "ok": False,
        "code": code,
        "message": message,
        "status": status_code,
    }


def _success(payload: dict):
    """Build a stable service success payload."""
    return {
        "ok": True,
        "payload": payload,
    }


def create_or_get_private_dialogue(*, acting_user, recipient, check_only=False):
    """
    Find existing DM or create a new one.

    Boundary policy:
    - Existing history is not deleted.
    - Direct interaction/open-for-action is blocked if Boundary exists.
    - This keeps the service safe even if a future endpoint bypasses View-level guards.
    """
    boundary_check = can_create_private_dialogue(
        acting_user=acting_user,
        recipient=recipient,
    )

    if not boundary_check.allowed:
        return _error(
            boundary_check.code,
            boundary_check.message,
            403,
        )

    dialogue = (
        Dialogue.objects.filter(participants=acting_user, is_group=False)
        .filter(participants=recipient)
        .first()
    )

    if dialogue:
        if dialogue.deleted_by_users.filter(id=acting_user.id).exists():
            dialogue.deleted_by_users.remove(acting_user)

        return _success({
            "dialogue": dialogue,
            "created": False,
            "message": "Dialogue already exists.",
        })

    if check_only:
        return _error("NOT_FOUND", "Dialogue does not exist.", 204)

    with transaction.atomic():
        dialogue = Dialogue.objects.create(is_group=False)
        dialogue.participants.add(acting_user, recipient)

        usernames = sorted([acting_user.username, recipient.username])
        dialogue.slug = Dialogue.generate_dialogue_slug(usernames)
        dialogue.save(update_fields=["slug"])

        DialogueParticipant.objects.create(
            dialogue=dialogue,
            user=acting_user,
            role="participant",
        )
        DialogueParticipant.objects.create(
            dialogue=dialogue,
            user=recipient,
            role="participant",
        )

    return _success({
        "dialogue": dialogue,
        "created": True,
        "message": "New dialogue created.",
    })


def create_group_dialogue(*, acting_user, group_name, group_image=None):
    """
    Create a new group dialogue with founder role.

    Boundary policy:
    - Creating a group with only the acting user has no conflict.
    - Adding future participants must be guarded in group participant services/views.
    """
    try:
        clean_name = validate_group_name(group_name)
    except DjangoValidationError as exc:
        return _error(
            "INVALID_GROUP_NAME",
            exc.messages[0] if exc.messages else "Invalid group name.",
            400,
        )

    if Dialogue.objects.filter(is_group=True, group_name__iexact=clean_name).exists():
        return _error(
            "DUPLICATE_GROUP_NAME",
            "A group with this name already exists.",
            400,
        )

    with transaction.atomic():
        dialogue = Dialogue.objects.create(
            is_group=True,
            group_name=clean_name,
        )

        if group_image:
            dialogue.group_image = group_image
            dialogue.group_avatar_version = (dialogue.group_avatar_version or 1) + 1
            dialogue.save(update_fields=["group_image", "group_avatar_version"])

        dialogue.participants.add(acting_user)

        DialogueParticipant.objects.create(
            dialogue=dialogue,
            user=acting_user,
            role="founder",
        )

        usernames = list(dialogue.participants.values_list("username", flat=True))
        dialogue.slug = Dialogue.generate_dialogue_slug(usernames, clean_name)
        dialogue.save(update_fields=["slug"])

    return _success({
        "dialogue": dialogue,
    })


def smart_delete_dialogue_for_user(*, dialogue, acting_user):
    """
    Smart delete for DM or group.

    Boundary policy:
    - Boundary does not delete existing history.
    - Users can still remove a dialogue from their own list.
    """
    if not dialogue.participants.filter(id=acting_user.id).exists():
        return _error("FORBIDDEN", "You are not a participant of this dialogue.", 403)

    # Private dialogue
    if not dialogue.is_group:
        with transaction.atomic():
            dialogue.mark_as_deleted_by_user(acting_user)

            for msg in dialogue.messages.all():
                msg.deleted_by_users.add(acting_user)

            other_participant = dialogue.participants.exclude(id=acting_user.id).first()
            permanently_deleted = False

            if other_participant and dialogue.deleted_by_users.filter(id=other_participant.id).exists():
                Message.objects.filter(dialogue=dialogue).delete()
                dialogue.delete()
                permanently_deleted = True

        if permanently_deleted:
            return _success({
                "dialogue_slug": None,
                "deleted_type": "permanent_dm",
                "message": "Dialogue permanently deleted.",
            })

        return _success({
            "dialogue_slug": dialogue.slug,
            "deleted_type": "soft_dm",
            "message": "Private chat deleted from your list.",
        })

    # Group dialogue
    participant = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=acting_user,
    ).first()

    if not participant:
        return _error("FORBIDDEN", "You are not a participant of this group.", 403)

    if participant.role != "founder":
        return _error(
            "FORBIDDEN",
            "Only the founder can delete the group. To leave, use the leave action.",
            403,
        )

    with transaction.atomic():
        Message.objects.filter(dialogue=dialogue).delete()
        DialogueParticipant.objects.filter(dialogue=dialogue).delete()
        dialogue.delete()

    return _success({
        "dialogue_slug": None,
        "deleted_type": "permanent_group",
        "message": "Group permanently deleted.",
    })