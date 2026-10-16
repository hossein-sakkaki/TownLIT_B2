# apps/conversation/services/organization/direct_realtime.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from __future__ import annotations

import base64

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.conversation.models import Message, OrganizationDialogueContext
from apps.conversation.services.message_media_descriptors import (
    build_message_media_descriptors,
)
from apps.conversation.services.message_reply import build_reply_preview
from apps.conversation.services.realtime_dispatch import (
    conv_group_send,
    conversation_user_group_name,
    simple_user_payload,
)
from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationPermissionKey,
    OrganizationRoleScope,
)
from apps.organizations.models import OrganizationMembership

from .availability import organization_messenger_is_available
from .direct_selectors import (
    organization_direct_total_unread_count,
    organization_direct_unread_count,
)

User = get_user_model()


def _organization_payload(organization) -> dict:
    return {
        "public_id": str(organization.public_id),
        "slug": organization.slug,
        "name": organization.name,
        "short_name": getattr(organization, "short_name", None),
        "brand_color": getattr(organization, "brand_color", None),
    }


def organization_direct_operator_user_ids(*, organization, now=None) -> list[int]:
    """Resolve current Organization Direct viewers without staff bypass."""
    if not organization_messenger_is_available(organization, now=now):
        return []

    now = now or timezone.now()
    return list(
        OrganizationMembership.objects
        .filter(
            organization=organization,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
            role_assignments__is_active=True,
            role_assignments__revoked_at__isnull=True,
            role_assignments__starts_at__lte=now,
            role_assignments__scope_type=OrganizationRoleScope.ORGANIZATION,
            role_assignments__scope_key="",
            role_assignments__role__is_active=True,
            role_assignments__role__role_permissions__permission__key__in=(
                OrganizationPermissionKey.VIEW_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
            role_assignments__role__role_permissions__permission__is_active=True,
        )
        .filter(
            Q(role_assignments__ends_at__isnull=True)
            | Q(role_assignments__ends_at__gt=now)
        )
        .values_list("member__user_id", flat=True)
        .distinct()
    )


def organization_direct_operator_users(*, organization, now=None):
    return User.objects.filter(
        id__in=organization_direct_operator_user_ids(
            organization=organization,
            now=now,
        )
    )


def _decode_plaintext(message) -> str:
    raw = getattr(message, "content_encrypted", None)
    if not raw:
        return ""
    try:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        return base64.b64decode(raw).decode("utf-8")
    except Exception:
        return ""


def _attribution(message):
    try:
        return message.organization_attribution
    except Exception:
        return None



def _message_file_type(message) -> str | None:
    if getattr(message, "image", None):
        return "image"
    if getattr(message, "video", None):
        return "video"
    if getattr(message, "audio", None):
        return "audio"
    if getattr(message, "file", None):
        return "file"
    return None

def build_organization_direct_message_payload(
    *,
    message,
    viewer=None,
    operator_view=False,
) -> dict:
    """Build a privacy-safe realtime payload for Organization Direct."""
    context = message.dialogue.organization_context
    organization = context.organization
    attribution = _attribution(message)
    plain_text = _decode_plaintext(message)

    reply_preview = build_reply_preview(
        message=message,
        acting_user=viewer,
    )

    payload = {
        "message_id": message.id,
        "dialogue_slug": message.dialogue.slug,
        "content": plain_text,
        "decrypted_content": plain_text,
        "timestamp": message.timestamp.isoformat(),
        "is_delivered": bool(getattr(message, "is_delivered", False)),
        "is_system": bool(getattr(message, "is_system", False)),
        "system_event": getattr(message, "system_event", None),
        "is_encrypted": False,
        "encrypted_for_device": None,
        "reply_to_message_id": getattr(message, "reply_to_id", None),
        "reply_preview": reply_preview,
        "is_forwarded": False,
        "forwarded_from_message_id": None,
        "forward_preview": None,
        "sender": None,
        "sender_type": "organization" if attribution else "user",
        "organization_attribution": None,
        "organization_context": {
            "type": context.context_type,
            "status": context.status,
            "waiting_for": context.waiting_for,
            "organization": _organization_payload(organization),
        },
    }

    file_type = _message_file_type(message)
    if file_type is not None:
        payload.update({
            "file_type": file_type,
            "has_file": True,
            "is_encrypted_file": False,
        })
        payload.update(build_message_media_descriptors(message))

    if attribution is None:
        payload["sender"] = simple_user_payload(message.sender)
        return payload

    attribution_payload = {
        "sent_as_organization": True,
        "organization": _organization_payload(organization),
        "actor": None,
        "actor_display_name": None,
        "actor_username": None,
        "actor_membership_public_id": None,
    }
    if operator_view:
        attribution_payload.update({
            "actor": simple_user_payload(message.sender),
            "actor_display_name": attribution.actor_display_name_snapshot,
            "actor_username": attribution.actor_username_snapshot,
            "actor_membership_public_id": (
                str(attribution.actor_membership_public_id_snapshot)
                if attribution.actor_membership_public_id_snapshot
                else None
            ),
        })
    payload["organization_attribution"] = attribution_payload
    return payload


def build_organization_direct_thread_state_payload(context, *, reason: str) -> dict:
    return {
        "reason": reason,
        "dialogue_slug": context.dialogue.slug,
        "context_public_id": str(context.public_id),
        "organization": _organization_payload(context.organization),
        "status": context.status,
        "waiting_for": context.waiting_for,
        "assigned_membership_public_id": (
            str(context.assigned_to_membership.public_id)
            if context.assigned_to_membership_id
            else None
        ),
    }


def _send_operator_unread_update(*, context, operator_user_id: int) -> None:
    operator = User.objects.filter(pk=operator_user_id).first()
    if not operator:
        return
    conv_group_send(
        conversation_user_group_name(operator_user_id),
        "organization_messenger_unread_update",
        {
            "mode": "incremental_authoritative",
            "organization": _organization_payload(context.organization),
            "dialogue_slug": context.dialogue.slug,
            "thread_unread_count": organization_direct_unread_count(
                context=context,
                operator_user=operator,
            ),
            "organization_unread_count": organization_direct_total_unread_count(
                organization=context.organization,
                operator_user=operator,
            ),
        },
    )


def _send_participant_unread_update(*, context) -> None:
    participant = context.participant_user
    unread_count = context.dialogue.unread_messages_for_user(participant).count()
    conv_group_send(
        conversation_user_group_name(participant.id),
        "unread_count_update",
        {
            "mode": "snapshot_patch",
            "payload": [{
                "dialogue_slug": context.dialogue.slug,
                "unread_count": unread_count,
            }],
        },
    )


def dispatch_organization_direct_thread_update(context_id: int, *, reason: str) -> None:
    context = (
        OrganizationDialogueContext.objects
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
            "assigned_to_membership",
        )
        .filter(pk=context_id)
        .first()
    )
    if not context:
        return

    data = build_organization_direct_thread_state_payload(
        context,
        reason=reason,
    )
    for user_id in organization_direct_operator_user_ids(
        organization=context.organization,
    ):
        conv_group_send(
            conversation_user_group_name(user_id),
            "organization_direct_thread_updated",
            data,
        )


def schedule_organization_direct_thread_update(context_id: int, *, reason: str) -> None:
    transaction.on_commit(
        lambda cid=context_id, why=reason: dispatch_organization_direct_thread_update(
            cid,
            reason=why,
        )
    )


def dispatch_organization_direct_message_realtime(message_id: int) -> None:
    message = (
        Message.objects
        .select_related(
            "sender",
            "dialogue__organization_context__organization",
            "dialogue__organization_context__participant_user",
            "dialogue__organization_context__assigned_to_membership",
            "organization_attribution__organization",
            "organization_attribution__actor_membership",
            "reply_to__sender",
        )
        .filter(pk=message_id)
        .first()
    )
    if not message or not message.is_delivery_ready:
        return

    context = message.dialogue.organization_context
    participant = context.participant_user
    attribution = _attribution(message)
    operator_ids = organization_direct_operator_user_ids(
        organization=context.organization,
    )

    # Participant sessions always receive their canonical thread echo/update.
    participant_payload = build_organization_direct_message_payload(
        message=message,
        viewer=participant,
        operator_view=False,
    )
    conv_group_send(
        conversation_user_group_name(participant.id),
        "chat_message",
        participant_payload,
    )

    if attribution is None:
        # External participant -> current authorized operators.
        operator_users = {
            user.id: user
            for user in User.objects.filter(id__in=operator_ids)
        }
        for user_id in operator_ids:
            operator = operator_users.get(user_id)
            if not operator:
                continue
            conv_group_send(
                conversation_user_group_name(user_id),
                "chat_message",
                build_organization_direct_message_payload(
                    message=message,
                    viewer=operator,
                    operator_view=True,
                ),
            )
            _send_operator_unread_update(
                context=context,
                operator_user_id=user_id,
            )
    else:
        # Organization reply -> participant is the message audience. Operators
        # receive a lightweight thread-state event so shared inboxes stay fresh.
        data = build_organization_direct_thread_state_payload(
            context,
            reason="organization_reply",
        )
        for user_id in operator_ids:
            conv_group_send(
                conversation_user_group_name(user_id),
                "organization_direct_thread_updated",
                data,
            )
        _send_participant_unread_update(context=context)


def schedule_organization_direct_message_realtime(message_id: int) -> None:
    transaction.on_commit(
        lambda mid=message_id: dispatch_organization_direct_message_realtime(mid)
    )


def dispatch_organization_direct_read_realtime(
    context_id: int,
    *,
    reader_id: int,
    read_message_ids: list[int],
) -> None:
    context = (
        OrganizationDialogueContext.objects
        .select_related("dialogue", "organization", "participant_user")
        .filter(pk=context_id)
        .first()
    )
    if not context:
        return

    reader_is_participant = reader_id == context.participant_user_id
    if reader_is_participant:
        for operator_id in organization_direct_operator_user_ids(
            organization=context.organization,
        ):
            conv_group_send(
                conversation_user_group_name(operator_id),
                "organization_direct_read",
                {
                    "dialogue_slug": context.dialogue.slug,
                    "reader_type": "participant",
                    "participant_user_id": context.participant_user_id,
                    "read_messages": list(read_message_ids),
                },
            )
        _send_participant_unread_update(context=context)
        return

    # External clients only learn the aggregate Organization identity.
    conv_group_send(
        conversation_user_group_name(context.participant_user_id),
        "organization_direct_seen",
        {
            "dialogue_slug": context.dialogue.slug,
            "read_messages": list(read_message_ids),
            "seen_by_organization": True,
        },
    )
    _send_operator_unread_update(
        context=context,
        operator_user_id=reader_id,
    )


def schedule_organization_direct_read_realtime(
    context_id: int,
    *,
    reader_id: int,
    read_message_ids: list[int],
) -> None:
    transaction.on_commit(
        lambda cid=context_id, rid=reader_id, mids=list(read_message_ids): (
            dispatch_organization_direct_read_realtime(
                cid,
                reader_id=rid,
                read_message_ids=mids,
            )
        )
    )


def organization_messenger_unread_snapshot_for_user(user) -> dict:
    """Build authoritative Organization Workspace unread state for reconnect."""
    if not user or not getattr(user, "is_authenticated", False):
        return {"mode": "snapshot", "organizations": [], "total_unread_count": 0}

    now = timezone.now()
    candidate_organizations = (
        OrganizationMembership.objects
        .filter(
            member__user=user,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
            role_assignments__is_active=True,
            role_assignments__revoked_at__isnull=True,
            role_assignments__starts_at__lte=now,
            role_assignments__scope_type=OrganizationRoleScope.ORGANIZATION,
            role_assignments__scope_key="",
            role_assignments__role__is_active=True,
            role_assignments__role__role_permissions__permission__key__in=(
                OrganizationPermissionKey.VIEW_MESSENGER,
                OrganizationPermissionKey.MANAGE_MESSENGER,
            ),
            role_assignments__role__role_permissions__permission__is_active=True,
        )
        .filter(
            Q(role_assignments__ends_at__isnull=True)
            | Q(role_assignments__ends_at__gt=now)
        )
        .select_related("organization")
        .values_list("organization_id", flat=True)
        .distinct()
    )

    from apps.organizations.models import Organization

    rows = []
    total = 0
    for organization in Organization.objects.filter(id__in=candidate_organizations):
        if not organization_messenger_is_available(organization, now=now):
            continue
        count = organization_direct_total_unread_count(
            organization=organization,
            operator_user=user,
        )
        rows.append({
            "organization": _organization_payload(organization),
            "unread_count": count,
        })
        total += count

    return {
        "mode": "snapshot",
        "organizations": rows,
        "total_unread_count": total,
    }

