# apps/conversation/services/group_domain.py

from django.db import transaction

from apps.conversation.models import DialogueParticipant


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


def build_group_role_changed_system_text(action: str, username: str) -> tuple[str, str]:
    """
    Build canonical system_event + text for group role changes.

    Supported actions:
    - promoted_to_elder
    - demoted_to_participant
    - resigned_from_elder
    """
    normalized = (action or "").strip()

    if normalized == "promoted_to_elder":
        return ("promoted_to_elder", f"{username} was promoted to Elder.")

    if normalized == "demoted_to_participant":
        return ("demoted_to_participant", f"{username} was demoted to Participant.")

    if normalized == "resigned_from_elder":
        return ("resigned_from_elder", f"{username} resigned from Elder role.")

    return ("group_update", f"{username} role was updated.")


def add_group_participant(*, dialogue, acting_user, target_user):
    """
    Add a user to a group if acting user is founder or elder.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    current_participant = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=acting_user,
    ).first()

    if not current_participant:
        return _error("FORBIDDEN", "You are not a member of this group.", 403)

    if current_participant.role not in ["founder", "elder"]:
        return _error("FORBIDDEN", "Only founders or elders can add new participants.", 403)

    if dialogue.participants.filter(id=target_user.id).exists():
        return _error("BAD_REQUEST", f"{target_user.username} is already a member of the group.", 400)

    with transaction.atomic():
        dialogue.participants.add(target_user)
        DialogueParticipant.objects.get_or_create(
            dialogue=dialogue,
            user=target_user,
            defaults={"role": "participant"},
        )

        if dialogue.deleted_by_users.filter(id=target_user.id).exists():
            dialogue.deleted_by_users.remove(target_user)

    return _success({
        "dialogue": dialogue,
        "participant": target_user,
    })


def remove_group_participant(*, dialogue, acting_user, target_user):
    """
    Remove a participant from a group if manager is allowed.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    if not dialogue.is_group_manager(acting_user):
        return _error("FORBIDDEN", "You are not authorized to remove participants.", 403)

    participant_role_obj = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=target_user,
    ).first()

    if not participant_role_obj:
        return _error("NOT_FOUND", "Target participant not found in this group.", 404)

    if participant_role_obj.role == "founder":
        return _error("BAD_REQUEST", "Cannot remove the founder from the group.", 400)

    if participant_role_obj.role == "elder" and not dialogue.has_multiple_elders():
        return _error("BAD_REQUEST", "Cannot remove the last elder from the group.", 400)

    with transaction.atomic():
        participant_role_obj.delete()
        dialogue.participants.remove(target_user)
        dialogue.mark_as_deleted_by_user(target_user)

        for msg in dialogue.messages.all():
            msg.deleted_by_users.add(target_user)

    return _success({
        "dialogue": dialogue,
        "participant": target_user,
    })


def promote_group_participant_to_elder(*, dialogue, acting_user, target_user_id):
    """
    Promote a participant to elder if acting user is founder.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    if not dialogue.is_founder(acting_user):
        return _error("FORBIDDEN", "Only the founder can promote to elder.", 403)

    participant = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user_id=target_user_id,
    ).first()

    if not participant:
        return _error("NOT_FOUND", "Target participant not found.", 404)

    participant.role = "elder"
    participant.save(update_fields=["role"])

    return _success({
        "dialogue": dialogue,
        "participant": participant.user,
    })


def demote_group_elder_to_participant(*, dialogue, acting_user, target_user_id):
    """
    Demote an elder to participant if acting user is founder.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    if not dialogue.is_founder(acting_user):
        return _error("FORBIDDEN", "Only the founder can demote elders.", 403)

    participant = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user_id=target_user_id,
    ).first()

    if not participant:
        return _error("NOT_FOUND", "Target participant not found.", 404)

    if participant.role != "elder":
        return _error("BAD_REQUEST", "User is not an elder.", 400)

    participant.role = "participant"
    participant.save(update_fields=["role"])

    return _success({
        "dialogue": dialogue,
        "participant": participant.user,
    })


def resign_group_elder_role(*, dialogue, acting_user):
    """
    Allow an elder to resign to participant role.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    participant = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=acting_user,
    ).first()

    if not participant:
        return _error("FORBIDDEN", "You are not a participant of this group.", 403)

    if participant.role != "elder":
        return _error("BAD_REQUEST", "You are not an elder.", 400)

    participant.role = "participant"
    participant.save(update_fields=["role"])

    return _success({
        "dialogue": dialogue,
        "participant": acting_user,
    })


def leave_group_as_participant(*, dialogue, acting_user):
    """
    Allow a normal participant to leave the group.
    Founder cannot leave; elder must resign first.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    participant = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=acting_user,
    ).first()

    if not participant:
        return _error("FORBIDDEN", "You are not a participant of this group.", 403)

    if participant.role == "founder":
        return _error("FORBIDDEN", "Founders cannot leave the group. You must delete the group instead.", 403)

    if participant.role == "elder":
        return _error("BAD_REQUEST", "You must first resign from being an Elder before leaving the group.", 400)

    with transaction.atomic():
        dialogue.leave_group(acting_user)

        for msg in dialogue.messages.all():
            msg.deleted_by_users.add(acting_user)

    return _success({
        "dialogue": dialogue,
        "participant": acting_user,
    })


def transfer_group_founder(*, dialogue, acting_user, new_founder_user_id):
    """
    Transfer founder role from current founder to an elder.
    """
    if not dialogue.is_group:
        return _error("BAD_REQUEST", "Target dialogue is not a group.", 400)

    if not dialogue.is_founder(acting_user):
        return _error("FORBIDDEN", "Only founder can transfer founder role.", 403)

    new_founder = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user_id=new_founder_user_id,
    ).first()

    if not new_founder:
        return _error("NOT_FOUND", "Target participant not found.", 404)

    if new_founder.role != "elder":
        return _error("BAD_REQUEST", "Only an Elder can be promoted to Founder.", 400)

    old_founder = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        user=acting_user,
    ).first()

    if not old_founder:
        return _error("NOT_FOUND", "Current founder role record not found.", 404)

    with transaction.atomic():
        old_founder.role = "participant"
        old_founder.save(update_fields=["role"])

        new_founder.role = "founder"
        new_founder.save(update_fields=["role"])

    return _success({
        "dialogue": dialogue,
        "old_founder": acting_user,
        "new_founder": new_founder.user,
    })