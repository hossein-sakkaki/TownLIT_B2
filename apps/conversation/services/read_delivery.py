# apps/conversation/services/read_delivery.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.services.realtime_access import get_dialogue_for_user


def _error(code: str, message: str, status_code: int):
    return {
        "ok": False,
        "code": code,
        "message": message,
        "status": status_code,
    }


def _success(payload: dict):
    return {
        "ok": True,
        "payload": payload,
    }


def _get_message_for_dialogue(dialogue, message_id):
    if not dialogue or not message_id:
        return None
    return dialogue.messages.filter(id=message_id).first()


def _mark_message_delivered_sync(message):
    if not message.is_delivered:
        message.is_delivered = True
        message.save(update_fields=["is_delivered"])


def _mark_message_read_sync(message, user):
    if user == message.sender:
        return
    if not message.seen_by_users.filter(id=user.id).exists():
        message.seen_by_users.add(user)


def build_mark_as_read_realtime_payload(payload: dict) -> dict:
    return {
        "dialogue_slug": payload["dialogue_slug"],
        "reader": payload["reader"],
        "read_messages": payload["read_messages"],
    }


def build_unread_count_snapshot_payload(results: list[dict]) -> dict:
    return {
        "mode": "snapshot",
        "payload": results,
    }


def mark_message_delivered_for_user(dialogue_slug, message_id, acting_user):
    if not dialogue_slug or not message_id:
        return _error(
            "BAD_REQUEST",
            "dialogue_slug and message_id are required.",
            400,
        )

    dialogue = get_dialogue_for_user(dialogue_slug, acting_user)
    if not dialogue:
        return _error("NOT_FOUND", "Dialogue not found.", 404)

    message = _get_message_for_dialogue(dialogue, message_id)
    if not message:
        return _error("NOT_FOUND", "Message not found.", 404)

    if message.sender_id == acting_user.id:
        return _error(
            "FORBIDDEN",
            "Sender cannot acknowledge delivery.",
            403,
        )

    context = ConversationContextPolicy.resolve(dialogue)
    if context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
        org_context = context.organization_context
        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=acting_user,
        )
        if not access.allowed:
            return _error(
                access.code or "FORBIDDEN",
                access.message or "Conversation access denied.",
                403,
            )

        acting_is_operator = acting_user.id != org_context.participant_user_id
        if acting_is_operator:
            # Operators may only acknowledge participant-originated traffic.
            if message.sender_id != org_context.participant_user_id:
                return _error("FORBIDDEN", "Message is not deliverable to this operator.", 403)
        else:
            # Participant may only acknowledge Organization-attributed replies.
            try:
                has_attribution = message.organization_attribution is not None
            except Exception:
                has_attribution = False
            if not has_attribution:
                return _error("FORBIDDEN", "Message is not an Organization reply.", 403)

        _mark_message_delivered_sync(message)
        return _success({
            "dialogue_slug": dialogue.slug,
            "message_id": message.id,
            "user_id": None if acting_is_operator else acting_user.id,
            "sender_id": message.sender_id,
            "is_delivered": True,
            "organization_direct": True,
            "delivered_to_organization": acting_is_operator,
            "participant_user_id": org_context.participant_user_id,
        })

    _mark_message_delivered_sync(message)
    return _success({
        "dialogue_slug": dialogue.slug,
        "message_id": message.id,
        "user_id": acting_user.id,
        "sender_id": message.sender_id,
        "is_delivered": True,
    })


def mark_dialogue_read_for_user(dialogue_slug, acting_user):
    if not dialogue_slug:
        return _error("BAD_REQUEST", "dialogue_slug is required.", 400)

    dialogue = get_dialogue_for_user(dialogue_slug, acting_user)
    if not dialogue:
        return _error("NOT_FOUND", "Dialogue not found.", 404)

    context = ConversationContextPolicy.resolve(dialogue)

    if context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
        org_context = context.organization_context
        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=acting_user,
        )
        if not access.allowed:
            return _error(
                access.code or "FORBIDDEN",
                access.message or "Conversation access denied.",
                403,
            )

        if acting_user.id == org_context.participant_user_id:
            unread_messages = list(
                dialogue.visible_messages_for_user(acting_user)
                .filter(organization_attribution__isnull=False)
                .exclude(seen_by_users=acting_user)
                .exclude(sender=acting_user)
            )
        else:
            from apps.conversation.services.organization.direct_selectors import (
                organization_direct_unread_queryset,
            )

            unread_messages = list(
                organization_direct_unread_queryset(
                    context=org_context,
                    operator_user=acting_user,
                )
            )

        for message in unread_messages:
            _mark_message_read_sync(message, acting_user)

        read_ids = [message.id for message in unread_messages]

        from apps.conversation.services.organization.direct_realtime import (
            schedule_organization_direct_read_realtime,
        )

        schedule_organization_direct_read_realtime(
            org_context.id,
            reader_id=acting_user.id,
            read_message_ids=read_ids,
        )

        return _success({
            "dialogue_slug": dialogue.slug,
            "reader": {
                "id": acting_user.id,
                "username": acting_user.username,
                "email": acting_user.email,
            },
            "read_messages": read_ids,
            "organization_direct": True,
            "reader_is_operator": acting_user.id != org_context.participant_user_id,
        })

    # Personal Direct, Personal Group and Members Community keep their existing
    # unread semantics, while Dialogue.unread_messages_for_user() supplies the
    # Community joined_at boundary.
    unread_messages = list(dialogue.unread_messages_for_user(acting_user))

    read_message_ids = []
    for message in unread_messages:
        _mark_message_read_sync(message, acting_user)
        read_message_ids.append(message.id)

    return _success({
        "dialogue_slug": dialogue.slug,
        "reader": {
            "id": acting_user.id,
            "username": acting_user.username,
            "email": acting_user.email,
        },
        "read_messages": read_message_ids,
    })
