# apps/sanctuary/services/safety_hold_status.py

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from apps.sanctuary.models import SanctuarySafetyHold
from apps.sanctuary.services.target_access import (
    get_target_object,
    resolve_target_owner_user_id,
)


OWNER_MESSAGE = (
    "This content is temporarily unavailable while a Sanctuary review "
    "is in progress."
)

PUBLIC_MESSAGE = ""


def _authenticated_user_id(user) -> int | None:
    if not user or not getattr(user, "is_authenticated", False):
        return None

    try:
        user_id = int(user.pk)
    except (TypeError, ValueError):
        return None

    return user_id if user_id > 0 else None


def _organization_manager_ids(organization) -> set[int]:
    user_ids: set[int] = set()

    try:
        user_ids.update(
            int(user_id)
            for user_id in organization.org_owners.filter(is_active=True)
            .values_list("user_id", flat=True)
            if user_id
        )
    except Exception:
        pass

    try:
        user_ids.update(
            int(user_id)
            for user_id in organization.admin_relationships.filter(
                is_approved=True,
                member__is_active=True,
            ).values_list("member__user_id", flat=True)
            if user_id
        )
    except Exception:
        pass

    return user_ids


def _is_sanctuary_staff(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    return bool(
        getattr(user, "is_admin", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    )
    
def _is_target_manager(*, user, request_type: str, target) -> bool:
    user_id = _authenticated_user_id(user)

    if not user_id:
        return False

    if _is_sanctuary_staff(user):
        return True

    if request_type in {"account", "content"}:
        return resolve_target_owner_user_id(target) == user_id

    if request_type == "organization":
        return user_id in _organization_manager_ids(target)

    if request_type == "messenger_group":
        try:
            return bool(target.is_group_manager(user))
        except Exception:
            return False

    return False


def get_sanctuary_target_status(
    *,
    user,
    request_type: str,
    content_type: ContentType,
    object_id: int,
) -> dict:
    """
    Return detailed hold information only to staff or target managers.

    Ordinary users always receive a neutral false state and never receive
    hold IDs, timestamps, reasons, request IDs, or internal workflow data.
    """
    target = get_target_object(
        content_type=content_type,
        object_id=object_id,
    )

    if target is None:
        return {
            "under_sanctuary_review": False,
            "status": None,
            "applied_at": None,
            "message": PUBLIC_MESSAGE,
        }

    can_manage = _is_target_manager(
        user=user,
        request_type=request_type,
        target=target,
    )

    if not can_manage:
        return {
            "under_sanctuary_review": False,
            "status": None,
            "applied_at": None,
            "message": PUBLIC_MESSAGE,
        }

    hold = (
        SanctuarySafetyHold.objects
        .filter(
            content_type=content_type,
            object_id=int(object_id),
            status=SanctuarySafetyHold.STATUS_ACTIVE,
            ended_at__isnull=True,
        )
        .only("status", "applied_at")
        .first()
    )

    if hold is None:
        return {
            "under_sanctuary_review": False,
            "status": None,
            "applied_at": None,
            "message": "",
        }

    return {
        "under_sanctuary_review": True,
        "status": hold.status,
        "applied_at": hold.applied_at,
        "message": OWNER_MESSAGE,
    }