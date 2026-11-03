# apps/posts/serializers/journey_owner.py
# TownLIT
# Created by Hossein Sakkaki on 2026-11-02.
# Last Update by Hossein Sakkaki on 2026-11-02.

from __future__ import annotations

from apps.accounts.mixins import AvatarURLMixin
from apps.accounts.models.user import CustomUser
from apps.profiles.models import GuestUser, Member
from apps.posts.serializers.serializers_owner_min import (
    build_owner_dto_from_content_object,
)


class _JourneyAvatarURLAdapter(AvatarURLMixin):
    def __init__(self, *, context):
        self.context = context or {}


def _owner_user(obj):
    target = getattr(obj, "content_object", None)
    if isinstance(target, CustomUser):
        return target
    if isinstance(target, (Member, GuestUser)):
        return target.user
    return None


def build_journey_owner_dto(obj, *, context=None):
    """Enrich Journey OwnerDTO only; other Post consumers stay unchanged."""
    payload = build_owner_dto_from_content_object(obj, context=context)
    if payload is None:
        return None

    user = _owner_user(obj)
    if user is None or user.pk != payload.get("id"):
        return payload

    adapter = _JourneyAvatarURLAdapter(context=context)
    payload["avatar_url"] = adapter.build_avatar_url(user)
    payload["avatar_cdn_url"] = adapter.build_avatar_cdn_url(user)
    payload["avatar_version"] = getattr(user, "avatar_version", None)

    label = payload.get("label") or {}
    if isinstance(label, dict):
        payload["label_color"] = label.get("color")
    else:
        payload["label_color"] = getattr(label, "color", None)

    full_name = " ".join(
        str(value).strip()
        for value in (getattr(user, "name", None), getattr(user, "family", None))
        if value
    ).strip()
    payload["full_name"] = full_name or user.username
    return payload
