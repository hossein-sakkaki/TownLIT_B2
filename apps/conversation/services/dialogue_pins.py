# apps/conversation/services/dialogue_pins.py

from django.db import transaction
from django.db.models import F, Max

from apps.conversation.models import DialoguePin


MAX_DIALOGUE_PINS = 5


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


def _is_dialogue_participant(dialogue, user) -> bool:
    """Check dialogue membership."""
    return dialogue.participants.filter(id=user.id).exists()


def _normalize_positions_for_user(user):
    """
    Normalize positions to 1..N.
    Keeps ordering stable and avoids gaps.
    """
    pins = list(
        DialoguePin.objects.filter(user=user)
        .select_related("dialogue")
        .order_by("position", "pinned_at", "id")
    )

    dirty = []
    expected = 1

    for pin in pins:
        if pin.position != expected:
            pin.position = expected
            dirty.append(pin)
        expected += 1

    if dirty:
        DialoguePin.objects.bulk_update(dirty, ["position"])


def pin_dialogue_for_user(*, dialogue, acting_user):
    """
    Pin one dialogue for one user.

    Rules:
    - user must be a participant
    - max 5 pinned dialogues
    - idempotent if already pinned
    """
    if not _is_dialogue_participant(dialogue, acting_user):
        return _error("FORBIDDEN", "You are not a participant of this dialogue.", 403)

    existing = DialoguePin.objects.filter(
        user=acting_user,
        dialogue=dialogue,
    ).first()

    if existing:
        return _success({
            "dialogue": dialogue,
            "pin": existing,
            "created": False,
            "message": "Dialogue is already pinned.",
        })

    current_count = DialoguePin.objects.filter(user=acting_user).count()
    if current_count >= MAX_DIALOGUE_PINS:
        return _error(
            "PIN_LIMIT_REACHED",
            f"You can pin at most {MAX_DIALOGUE_PINS} dialogues.",
            400,
        )

    next_position = current_count + 1

    with transaction.atomic():
        pin = DialoguePin.objects.create(
            user=acting_user,
            dialogue=dialogue,
            position=next_position,
        )

    return _success({
        "dialogue": dialogue,
        "pin": pin,
        "created": True,
        "message": "Dialogue pinned successfully.",
    })


def unpin_dialogue_for_user(*, dialogue, acting_user):
    """
    Unpin one dialogue for one user.

    Rules:
    - user must be a participant
    - idempotent error if not pinned
    - remaining pins are compacted
    """
    if not _is_dialogue_participant(dialogue, acting_user):
        return _error("FORBIDDEN", "You are not a participant of this dialogue.", 403)

    pin = DialoguePin.objects.filter(
        user=acting_user,
        dialogue=dialogue,
    ).first()

    if not pin:
        return _error("NOT_PINNED", "Dialogue is not pinned.", 404)

    removed_position = pin.position

    with transaction.atomic():
        pin.delete()

        DialoguePin.objects.filter(
            user=acting_user,
            position__gt=removed_position,
        ).update(position=F("position") - 1)

        _normalize_positions_for_user(acting_user)

    return _success({
        "dialogue": dialogue,
        "removed_position": removed_position,
        "message": "Dialogue unpinned successfully.",
    })


def list_pinned_dialogues_for_user(*, acting_user):
    """
    Return ordered pinned dialogues for one user.
    """
    pins = list(
        DialoguePin.objects.filter(user=acting_user)
        .select_related("dialogue")
        .order_by("position", "pinned_at", "id")
    )

    return _success({
        "pins": pins,
        "count": len(pins),
    })


def get_next_pin_position_for_user(*, acting_user):
    """
    Helper for future reorder/insert workflows.
    """
    max_position = (
        DialoguePin.objects.filter(user=acting_user)
        .aggregate(max_pos=Max("position"))
        .get("max_pos")
    ) or 0

    return min(max_position + 1, MAX_DIALOGUE_PINS)