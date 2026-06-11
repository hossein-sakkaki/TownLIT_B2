# apps/posts/services/boundary_interactions.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.contrib.contenttypes.models import ContentType

from apps.core.boundaries.constants import BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE
from apps.core.boundaries.services.policy import BoundaryPolicy


CONTENT_INTERACTION_UNAVAILABLE_CODE = "content_interaction_unavailable"


@dataclass(frozen=True)
class ContentInteractionBoundaryCheck:
    allowed: bool
    message: str = ""
    code: str = ""
    counterpart_id: int | None = None


def _allowed() -> ContentInteractionBoundaryCheck:
    return ContentInteractionBoundaryCheck(allowed=True)


def _blocked(counterpart_id: int | None = None) -> ContentInteractionBoundaryCheck:
    return ContentInteractionBoundaryCheck(
        allowed=False,
        message=BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
        code=CONTENT_INTERACTION_UNAVAILABLE_CODE,
        counterpart_id=counterpart_id,
    )


def content_interaction_error_payload(
    *,
    message: str = BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
    code: str = CONTENT_INTERACTION_UNAVAILABLE_CODE,
) -> dict:
    return {
        "error": message,
        "code": code,
    }


def _coerce_object_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def get_target_object(*, content_type: ContentType, object_id):
    """
    Safely resolve a generic target object from ContentType + object_id.
    Returns None if the target no longer exists.
    """
    if not content_type or object_id is None:
        return None

    model_cls = content_type.model_class()
    if model_cls is None:
        return None

    try:
        return model_cls._default_manager.get(pk=_coerce_object_id(object_id))
    except model_cls.DoesNotExist:
        return None
    except Exception:
        return None


def resolve_owner_user(obj):
    """
    Resolve the real owner user from post-like or wrapper objects.

    Supports:
    - direct user/name/owner/author fields
    - GenericForeignKey wrappers through content_object
    - Member/Guest profile objects with .user
    - Organization-like objects with org_owners fallback
    """
    if not obj:
        return None

    # If object wraps another object, prefer inner content owner.
    try:
        inner = getattr(obj, "content_object", None)
        if inner is not None and inner is not obj:
            inner_owner = resolve_owner_user(inner)
            if inner_owner is not None:
                return inner_owner
    except Exception:
        pass

    for attr in (
        "user",
        "name",
        "owner",
        "author",
        "created_by",
        "member_user",
        "org_owner_user",
    ):
        try:
            value = getattr(obj, attr, None)
            if value is not None and hasattr(value, "id"):
                return value
        except Exception:
            continue

    # Organization-like fallback: use first active owner if available.
    try:
        org_owners = getattr(obj, "org_owners", None)
        if org_owners is not None:
            return org_owners.filter(is_active=True).first()
    except Exception:
        pass

    return None


def _boundary_between(actor, counterpart) -> ContentInteractionBoundaryCheck:
    """
    Shared direct-interaction rule:
    Boundary in either direction blocks new content interaction.
    """
    if not actor or not counterpart:
        return _allowed()

    if getattr(actor, "id", None) == getattr(counterpart, "id", None):
        return _allowed()

    if BoundaryPolicy.has_boundary_between(actor, counterpart):
        return _blocked(counterpart_id=getattr(counterpart, "id", None))

    return _allowed()


def check_target_owner_boundary(
    *,
    actor,
    content_type: ContentType,
    object_id,
) -> ContentInteractionBoundaryCheck:
    """
    Block new interaction with content owned by a user who has Boundary
    with the actor in either direction.
    """
    target_obj = get_target_object(
        content_type=content_type,
        object_id=object_id,
    )

    owner = resolve_owner_user(target_obj)

    return _boundary_between(actor, owner)


def check_comment_create_boundary(
    *,
    actor,
    content_type: ContentType,
    object_id,
    parent_comment=None,
) -> ContentInteractionBoundaryCheck:
    """
    Comment create rules:

    Root comment:
    - Block if actor has Boundary with the content owner.

    Reply:
    - Block if actor has Boundary with the content owner.
    - Block if actor has Boundary with the parent comment author.
    """
    target_check = check_target_owner_boundary(
        actor=actor,
        content_type=content_type,
        object_id=object_id,
    )

    if not target_check.allowed:
        return target_check

    if parent_comment is not None:
        parent_author = getattr(parent_comment, "name", None)
        parent_check = _boundary_between(actor, parent_author)

        if not parent_check.allowed:
            return parent_check

    return _allowed()


def check_comment_update_boundary(*, actor, comment) -> ContentInteractionBoundaryCheck:
    """
    Editing an old comment can become a new direct interaction.
    Therefore, if Boundary exists with content owner or parent author,
    editing is blocked.

    Deleting your own old comment should stay allowed and is handled
    outside this service.
    """
    if not comment:
        return _allowed()

    target_check = check_target_owner_boundary(
        actor=actor,
        content_type=comment.content_type,
        object_id=comment.object_id,
    )

    if not target_check.allowed:
        return target_check

    parent_comment = getattr(comment, "recomment", None)
    if parent_comment is not None:
        parent_author = getattr(parent_comment, "name", None)
        parent_check = _boundary_between(actor, parent_author)

        if not parent_check.allowed:
            return parent_check

    return _allowed()


def check_reaction_create_boundary(
    *,
    actor,
    content_type: ContentType,
    object_id,
) -> ContentInteractionBoundaryCheck:
    """
    Reaction create/change is a new interaction with the content owner.
    Boundary blocks it.
    """
    return check_target_owner_boundary(
        actor=actor,
        content_type=content_type,
        object_id=object_id,
    )