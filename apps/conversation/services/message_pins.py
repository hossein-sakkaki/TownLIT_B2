# apps/conversation/services/message_pins.py

from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.conversation.models import Message, MessagePin
from apps.conversation.constants import (
    PIN_NONE,
    PIN_1_HOUR,
    PIN_24_HOURS,
    PIN_1_WEEK,
    PIN_1_MONTH,
    PIN_3_MONTHS,
)


MAX_MESSAGE_PINS_PER_DIALOGUE = 5


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


def _normalize_message_pin_positions(dialogue):
    """
    Normalize positions to 1..N inside one dialogue.
    """
    pins = list(
        MessagePin.objects.filter(dialogue=dialogue)
        .select_related("message", "pinned_by")
        .order_by("position", "created_at", "id")
    )

    dirty = []
    expected = 1

    for pin in pins:
        if pin.position != expected:
            pin.position = expected
            dirty.append(pin)
        expected += 1

    if dirty:
        MessagePin.objects.bulk_update(dirty, ["position"])


def _duration_to_expiry_and_interval(pin_duration: str):
    """
    Resolve expiry datetime and reminder interval.
    """
    now = timezone.now()
    normalized = (pin_duration or PIN_NONE).strip()

    if normalized == PIN_NONE:
        return None, None

    if normalized == PIN_1_HOUR:
        return now + timedelta(hours=1), 15

    if normalized == PIN_24_HOURS:
        return now + timedelta(hours=24), 6 * 60

    if normalized == PIN_1_WEEK:
        return now + timedelta(days=7), 24 * 60

    if normalized == PIN_1_MONTH:
        return now + timedelta(days=30), 7 * 24 * 60

    if normalized == PIN_3_MONTHS:
        return now + timedelta(days=90), 30 * 24 * 60

    return None, None


def _can_pin_in_dialogue(dialogue, acting_user) -> bool:
    """Any participant can pin in DM; only participants can pin in group."""
    return dialogue.participants.filter(id=acting_user.id).exists()


def _is_message_visible_to_user(message, acting_user) -> bool:
    """Pinned target must be visible to the actor."""
    if not message.dialogue.participants.filter(id=acting_user.id).exists():
        return False

    if message.deleted_by_users.filter(id=acting_user.id).exists():
        return False

    return True


def pin_message_for_dialogue(*, message_id, acting_user, pin_duration=PIN_NONE, reminders_enabled=False):
    """
    Create one shared message pin in a dialogue.

    Rules:
    - actor must be a participant
    - target message must be visible to actor
    - max 5 active pins per dialogue
    - shared across the dialogue
    - reminders are sent only to pinned_by
    """
    try:
        message = Message.objects.select_related("dialogue", "sender").get(id=message_id)
    except Message.DoesNotExist:
        return _error("NOT_FOUND", "Message not found.", 404)

    dialogue = message.dialogue

    if not _can_pin_in_dialogue(dialogue, acting_user):
        return _error("FORBIDDEN", "You are not a participant of this dialogue.", 403)

    if not _is_message_visible_to_user(message, acting_user):
        return _error("FORBIDDEN", "Target message is not visible to you.", 403)

    existing = MessagePin.objects.filter(dialogue=dialogue, message=message).first()
    if existing:
        return _success({
            "pin": existing,
            "message": message,
            "dialogue": dialogue,
            "created": False,
            "result_message": "Message is already pinned.",
        })

    current_count = MessagePin.objects.filter(dialogue=dialogue).count()
    if current_count >= MAX_MESSAGE_PINS_PER_DIALOGUE:
        return _error(
            "PIN_LIMIT_REACHED",
            f"Only {MAX_MESSAGE_PINS_PER_DIALOGUE} pinned messages are allowed per dialogue.",
            400,
        )

    expires_at, reminder_interval = _duration_to_expiry_and_interval(pin_duration)
    next_reminder_at = None

    if reminders_enabled and reminder_interval and expires_at:
        next_reminder_at = timezone.now() + timedelta(minutes=reminder_interval)

    with transaction.atomic():
        pin = MessagePin.objects.create(
            dialogue=dialogue,
            message=message,
            pinned_by=acting_user,
            position=current_count + 1,
            pin_duration=pin_duration,
            expires_at=expires_at,
            reminders_enabled=bool(reminders_enabled and reminder_interval and expires_at),
            reminder_interval_minutes=reminder_interval,
            next_reminder_at=next_reminder_at,
        )

    return _success({
        "pin": pin,
        "message": message,
        "dialogue": dialogue,
        "created": True,
        "result_message": "Message pinned successfully.",
    })


def unpin_message_for_dialogue(*, message_id, acting_user):
    """
    Remove one shared message pin from a dialogue.
    """
    try:
        message = Message.objects.select_related("dialogue").get(id=message_id)
    except Message.DoesNotExist:
        return _error("NOT_FOUND", "Message not found.", 404)

    dialogue = message.dialogue

    if not _can_pin_in_dialogue(dialogue, acting_user):
        return _error("FORBIDDEN", "You are not a participant of this dialogue.", 403)

    pin = MessagePin.objects.filter(dialogue=dialogue, message=message).first()
    if not pin:
        return _error("NOT_PINNED", "Message is not pinned.", 404)

    removed_position = pin.position

    with transaction.atomic():
        pin.delete()

        MessagePin.objects.filter(
            dialogue=dialogue,
            position__gt=removed_position,
        ).update(position=F("position") - 1)

        _normalize_message_pin_positions(dialogue)

    return _success({
        "dialogue": dialogue,
        "message": message,
        "removed_position": removed_position,
        "result_message": "Message unpinned successfully.",
    })


def list_pinned_messages_for_dialogue(*, dialogue, acting_user):
    """
    Return all active pinned messages for one dialogue.
    """
    if not _can_pin_in_dialogue(dialogue, acting_user):
        return _error("FORBIDDEN", "You are not a participant of this dialogue.", 403)

    pins = list(
        MessagePin.objects.filter(dialogue=dialogue)
        .select_related("message", "message__sender", "pinned_by")
        .order_by("position", "created_at", "id")
    )

    return _success({
        "dialogue": dialogue,
        "pins": pins,
        "count": len(pins),
    })


def expire_due_message_pins():
    """
    Remove expired pins and compact positions.
    Returns list of affected dialogue ids for optional downstream sync.
    """
    now = timezone.now()
    expired_pins = list(
        MessagePin.objects.filter(expires_at__isnull=False, expires_at__lte=now)
        .select_related("dialogue", "message", "pinned_by")
        .order_by("dialogue_id", "position", "id")
    )

    if not expired_pins:
        return _success({
            "expired_count": 0,
            "dialogue_ids": [],
        })

    affected_dialogue_ids = sorted({pin.dialogue_id for pin in expired_pins})

    with transaction.atomic():
        MessagePin.objects.filter(id__in=[pin.id for pin in expired_pins]).delete()

        from apps.conversation.models import Dialogue
        for dialogue in Dialogue.objects.filter(id__in=affected_dialogue_ids):
            _normalize_message_pin_positions(dialogue)

    return _success({
        "expired_count": len(expired_pins),
        "dialogue_ids": affected_dialogue_ids,
    })


def collect_due_pin_reminders(limit=500):
    """
    Collect reminder-eligible pins and move next_reminder_at forward.
    """
    now = timezone.now()

    due_pins = list(
        MessagePin.objects.filter(
            reminders_enabled=True,
            expires_at__isnull=False,
            expires_at__gt=now,
            next_reminder_at__isnull=False,
            next_reminder_at__lte=now,
        )
        .select_related("dialogue", "message", "message__sender", "pinned_by")
        .order_by("next_reminder_at", "id")[:limit]
    )

    sent_pin_ids = []

    with transaction.atomic():
        for pin in due_pins:
            interval = pin.reminder_interval_minutes
            if not interval:
                continue

            pin.last_reminded_at = now
            pin.next_reminder_at = now + timedelta(minutes=interval)
            pin.save(update_fields=["last_reminded_at", "next_reminder_at"])
            sent_pin_ids.append(pin.id)

    return _success({
        "pins": due_pins,
        "count": len(sent_pin_ids),
    })