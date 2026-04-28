# apps/core/interactions/services/reaction_realtime.py

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.contenttypes.models import ContentType

from apps.posts.models.reaction import Reaction

logger = logging.getLogger(__name__)


def _content_type_key(ct: ContentType) -> str:
    """
    Use canonical public interaction key.
    Keep app_label.model to match frontend Redux keys.
    Example: "posts.moment"
    """
    return f"{ct.app_label}.{ct.model}"


def _target_group_name(ct_id: int, object_id: int) -> str:
    return f"reactions.target.{ct_id}.{object_id}"


def _inbox_group_name(ct_id: int, object_id: int, user_id: int) -> str:
    return f"reactions.inbox.{ct_id}.{object_id}.{user_id}"


def build_reaction_summary_payload(*, content_type, object_id):
    model_class = content_type.model_class()
    if not model_class:
        return None

    target = (
        model_class.objects
        .filter(pk=object_id)
        .values("reactions_count", "reactions_breakdown")
        .first()
    )
    if not target:
        return None

    return {
        "content_type": _content_type_key(content_type),
        "content_type_id": int(content_type.id),
        "object_id": int(object_id),
        "reactions_count": int(target.get("reactions_count") or 0),
        "reactions_breakdown": target.get("reactions_breakdown") or {},
        # Realtime summary is object-level, not per-user.
        "my_reaction": None,
    }


def _safe_user_payload(user):
    """
    Build a defensive user payload without assuming optional fields exist.
    """
    if not user:
        return None

    payload = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
    }

    # Optional fields
    for field in (
        "name",
        "family",
        "avatar_url",
        "profile_image",
        "avatar_cdn_url",
        "profile_url",
    ):
        if hasattr(user, field):
            payload[field] = getattr(user, field, None)

    return payload


def build_reaction_inbox_payload(*, content_type, object_id):
    """
    Owner inbox payload for reactions that include a message.
    """
    qs = (
        Reaction.objects
        .filter(
            content_type=content_type,
            object_id=object_id,
        )
        .exclude(message__isnull=True)
        .exclude(message__exact="")
        .select_related("name")
        .order_by("-timestamp")
    )

    items = []
    for reaction in qs:
        items.append({
            "id": reaction.id,
            "reaction_type": reaction.reaction_type,
            "message": reaction.message,
            "timestamp": reaction.timestamp.isoformat() if reaction.timestamp else None,
            "content_type": _content_type_key(content_type),
            "object_id": reaction.object_id,
            "user": _safe_user_payload(getattr(reaction, "name", None)),
        })

    return {
        "content_type": _content_type_key(content_type),
        "content_type_id": int(content_type.id),
        "object_id": int(object_id),
        "items": items,
    }


def broadcast_reaction_summary_changed(*, content_type, object_id):
    try:
        payload = build_reaction_summary_payload(
            content_type=content_type,
            object_id=object_id,
        )
        if not payload:
            return

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        async_to_sync(channel_layer.group_send)(
            _target_group_name(content_type.id, object_id),
            {
                "type": "dispatch_event",
                "app": "reactions",
                "event": "summary_changed",
                "data": payload,
            },
        )
    except Exception as e:
        logger.exception(
            "[reaction_realtime] broadcast_reaction_summary_changed failed: %s",
            e,
        )


def broadcast_reaction_inbox_changed(*, content_type, object_id, owner_user_id: int | None):
    try:
        if not owner_user_id:
            return

        payload = build_reaction_inbox_payload(
            content_type=content_type,
            object_id=object_id,
        )

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        async_to_sync(channel_layer.group_send)(
            _inbox_group_name(content_type.id, object_id, owner_user_id),
            {
                "type": "dispatch_event",
                "app": "reactions",
                "event": "inbox_changed",
                "data": payload,
            },
        )
    except Exception as e:
        logger.exception(
            "[reaction_realtime] broadcast_reaction_inbox_changed failed: %s",
            e,
        )


def resolve_owner_user_id(obj):
    base = obj

    if hasattr(base, "content_object") and getattr(base, "content_object") is not None:
        base = base.content_object

    for fk in ("user_id", "name_id", "owner_id", "member_user_id", "org_owner_user_id"):
        if hasattr(base, fk):
            val = getattr(base, fk)
            if isinstance(val, int):
                return val

    if base.__class__.__name__.lower() == "member" and hasattr(base, "user_id"):
        return getattr(base, "user_id", None)

    for rel in ("name", "owner", "member_user", "org_owner_user"):
        if hasattr(base, rel):
            rel_obj = getattr(base, rel)
            if getattr(rel_obj, "id", None):
                return rel_obj.id

    return None