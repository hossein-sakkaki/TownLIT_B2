# apps/sanctuary/services/target_access.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.core.visibility.policy import VisibilityPolicy
from apps.sanctuary.constants.target_models import (
    content_type_key,
    is_allowed_target_model,
)


CustomUser = get_user_model()


TARGET_NOT_FOUND = "target_not_found"
TARGET_NOT_AVAILABLE = "target_not_available"
TARGET_NOT_VISIBLE = "target_not_visible"
SELF_TARGET_NOT_ALLOWED = "self_target_not_allowed"
GROUP_MEMBERSHIP_REQUIRED = "group_membership_required"
INVALID_GROUP_TARGET = "invalid_group_target"
INVALID_TARGET_MODEL = "invalid_target_model"


@dataclass(frozen=True)
class SanctuaryTargetAccessResult:
    target: Any
    content_type: ContentType
    content_type_key: str
    object_id: int
    owner_user_id: int | None
    is_owner: bool


def _raise_access_error(
    *,
    message: str,
    code: str,
    field: str = "detail",
) -> None:
    """
    Raise a stable DRF validation error.

    `code` is intentionally returned separately so iOS can later
    map server errors without parsing human-readable text.
    """

    raise serializers.ValidationError(
        {
            field: message,
            "code": code,
        }
    )


def resolve_content_type_key(
    value: str,
) -> ContentType:
    """
    Resolve `app_label.model` case-insensitively.
    """

    normalized = str(value or "").strip().lower()

    if (
        not normalized
        or normalized.count(".") != 1
    ):
        _raise_access_error(
            message=(
                "content_type must be in format "
                "'app_label.model'."
            ),
            code=INVALID_TARGET_MODEL,
            field="content_type",
        )

    app_label, model = normalized.split(
        ".",
        1,
    )

    app_label = app_label.strip()
    model = model.strip()

    if not app_label or not model:
        _raise_access_error(
            message=(
                "content_type must be in format "
                "'app_label.model'."
            ),
            code=INVALID_TARGET_MODEL,
            field="content_type",
        )

    try:
        return ContentType.objects.get(
            app_label__iexact=app_label,
            model__iexact=model,
        )
    except (
        ContentType.DoesNotExist,
        ContentType.MultipleObjectsReturned,
    ):
        _raise_access_error(
            message="Invalid content_type.",
            code=INVALID_TARGET_MODEL,
            field="content_type",
        )


def get_target_object(
    *,
    content_type: ContentType,
    object_id: int,
):
    """
    Resolve an allow-listed generic target safely.
    """

    model_class = content_type.model_class()

    if model_class is None:
        _raise_access_error(
            message="Invalid target model.",
            code=INVALID_TARGET_MODEL,
            field="content_type",
        )

    try:
        normalized_object_id = int(
            object_id
        )
    except (
        TypeError,
        ValueError,
    ):
        _raise_access_error(
            message="Invalid target object ID.",
            code=TARGET_NOT_FOUND,
            field="object_id",
        )

    if normalized_object_id < 1:
        _raise_access_error(
            message="Invalid target object ID.",
            code=TARGET_NOT_FOUND,
            field="object_id",
        )

    try:
        return (
            model_class._default_manager
            .filter(
                pk=normalized_object_id
            )
            .first()
        )
    except Exception:
        _raise_access_error(
            message=(
                "The selected Sanctuary target "
                "could not be resolved."
            ),
            code=TARGET_NOT_FOUND,
            field="object_id",
        )


def _authenticated_user_id(
    user,
) -> int | None:
    if not user:
        return None

    if not getattr(
        user,
        "is_authenticated",
        False,
    ):
        return None

    try:
        user_id = int(user.pk)
    except (
        TypeError,
        ValueError,
    ):
        return None

    return user_id if user_id > 0 else None


def _profile_user_id(
    obj,
) -> int | None:
    """
    Resolve Member/Guest-like `.user_id`.
    """

    try:
        value = getattr(
            obj,
            "user_id",
            None,
        )

        if value:
            return int(value)
    except (
        TypeError,
        ValueError,
        Exception,
    ):
        return None

    return None


def _target_model_key(
    target,
) -> str:
    """
    Return the canonical Django model key for a resolved target.

    Example:
        posts.comment
    """

    if target is None:
        return ""

    try:
        meta = target.__class__._meta

        app_label = str(
            meta.app_label
            or ""
        ).strip().lower()

        model_name = str(
            meta.model_name
            or ""
        ).strip().lower()

        if app_label and model_name:
            return f"{app_label}.{model_name}"
    except Exception:
        pass

    return ""


def _is_comment_target(
    target,
) -> bool:
    """
    Comment and Reply use the same backend model.

    A Reply is distinguished by `recomment_id`, but its Sanctuary
    ContentType remains `posts.comment`.
    """

    return (
        _target_model_key(target)
        == "posts.comment"
    )


def _comment_author_user_id(
    comment,
) -> int | None:
    """
    Resolve the author of a Comment or Reply.

    The Comment model stores its author in `name_id`.
    The parent post owner must never be treated as the owner of the
    Comment Sanctuary target.
    """

    try:
        user_id = getattr(
            comment,
            "name_id",
            None,
        )

        if user_id:
            normalized = int(user_id)

            if normalized > 0:
                return normalized
    except (
        TypeError,
        ValueError,
        Exception,
    ):
        pass

    try:
        author = getattr(
            comment,
            "name",
            None,
        )

        user_id = getattr(
            author,
            "pk",
            None,
        )

        if user_id:
            normalized = int(user_id)

            if normalized > 0:
                return normalized
    except (
        TypeError,
        ValueError,
        Exception,
    ):
        pass

    return None


def _comment_visibility_target(
    comment,
):
    """
    Resolve the parent content whose visibility governs the Comment.

    Sanctuary still targets the Comment itself, but a visitor may
    submit the request only when they can view the parent content.
    """

    try:
        content_object = getattr(
            comment,
            "content_object",
            None,
        )

        if (
            content_object is not None
            and content_object is not comment
        ):
            return content_object
    except Exception:
        pass

    return None


def _organization_owner_user_ids(
    organization,
) -> set[int]:
    """
    Resolve organization owners and approved admins to user IDs.
    """

    user_ids: set[int] = set()

    try:
        owner_ids = (
            organization.org_owners
            .filter(
                is_active=True,
            )
            .values_list(
                "user_id",
                flat=True,
            )
        )

        user_ids.update(
            int(user_id)
            for user_id in owner_ids
            if user_id
        )
    except Exception:
        pass

    try:
        admin_ids = (
            organization.admin_relationships
            .filter(
                is_approved=True,
                member__is_active=True,
            )
            .values_list(
                "member__user_id",
                flat=True,
            )
        )

        user_ids.update(
            int(user_id)
            for user_id in admin_ids
            if user_id
        )
    except Exception:
        pass

    return user_ids


def resolve_target_owner_user_id(
    target,
) -> int | None:
    """
    Resolve the primary user owner for account/content targets.

    Supported:
    - CustomUser
    - Comment / Reply author
    - Member / GuestUser
    - JourneyEntry.owner_user
    - post-like GenericForeignKey owners
    - direct user-like relations

    Important:
    - A Comment or Reply belongs to its author (`name_id`).
    - Its parent post owner is not the owner of the Comment target.

    Organization can have multiple owners, so organization ownership is
    handled separately.
    """

    if target is None:
        return None

    if isinstance(
        target,
        CustomUser,
    ):
        return _authenticated_user_id(
            target
        )

    # Comment and Reply must resolve to their own author before
    # inspecting the GenericForeignKey parent content.
    if _is_comment_target(
        target
    ):
        return _comment_author_user_id(
            target
        )

    profile_user_id = _profile_user_id(
        target
    )

    if profile_user_id:
        return profile_user_id

    try:
        owner_user = getattr(
            target,
            "owner_user",
            None,
        )

        if owner_user is not None:
            owner_user_id = getattr(
                owner_user,
                "pk",
                None,
            )

            if owner_user_id:
                return int(
                    owner_user_id
                )
    except Exception:
        pass

    try:
        content_object = getattr(
            target,
            "content_object",
            None,
        )

        if (
            content_object is not None
            and content_object is not target
        ):
            return resolve_target_owner_user_id(
                content_object
            )
    except Exception:
        pass

    for attribute_name in (
        "user",
        "owner",
        "author",
        "created_by",
        "name",
        "member_user",
        "org_owner_user",
    ):
        try:
            related = getattr(
                target,
                attribute_name,
                None,
            )

            related_id = getattr(
                related,
                "pk",
                None,
            )

            if related_id:
                return int(
                    related_id
                )
        except Exception:
            continue

    return None


def _is_deleted_account(
    target,
) -> bool:
    return bool(
        getattr(
            target,
            "is_deleted",
            False,
        )
    )


def _is_unavailable_content(
    target,
) -> bool:
    """
    Moderated, hidden, suspended, or incomplete content must not
    accept new Sanctuary requests.

    Availability is checked only when the model exposes a callable
    `is_available()` contract.
    """

    if not bool(
        getattr(
            target,
            "is_active",
            True,
        )
    ):
        return True

    if bool(
        getattr(
            target,
            "is_hidden",
            False,
        )
    ):
        return True

    if bool(
        getattr(
            target,
            "is_suspended",
            False,
        )
    ):
        return True

    availability_method = getattr(
        target,
        "is_available",
        None,
    )

    if callable(
        availability_method
    ):
        try:
            if not bool(
                availability_method()
            ):
                return True
        except Exception:
            return True

    return False


def _validate_account_target(
    *,
    user,
    target,
    allow_self_target: bool = False,
) -> tuple[int | None, bool]:
    user_id = _authenticated_user_id(
        user
    )

    target_user_id = _authenticated_user_id(
        target
    )

    if _is_deleted_account(
        target
    ):
        _raise_access_error(
            message=(
                "This account is no longer "
                "available."
            ),
            code=TARGET_NOT_AVAILABLE,
        )

    is_owner = bool(
        user_id
        and target_user_id
        and user_id == target_user_id
    )

    if is_owner and not allow_self_target:
        _raise_access_error(
            message=(
                "You cannot submit a Sanctuary "
                "request for your own account."
            ),
            code=SELF_TARGET_NOT_ALLOWED,
        )

    return (
        target_user_id,
        is_owner,
    )


def _validate_content_target(
    *,
    user,
    target,
    allow_self_target: bool = False,
) -> tuple[int | None, bool]:
    user_id = _authenticated_user_id(
        user
    )

    owner_user_id = (
        resolve_target_owner_user_id(
            target
        )
    )

    is_owner = bool(
        user_id
        and owner_user_id
        and user_id == owner_user_id
    )

    if is_owner and not allow_self_target:
        _raise_access_error(
            message=(
                "You cannot submit a Sanctuary "
                "request for your own content."
            ),
            code=SELF_TARGET_NOT_ALLOWED,
        )

    # The Comment/Reply itself must still be active and available.
    if _is_unavailable_content(
        target
    ):
        _raise_access_error(
            message=(
                "This content is no longer "
                "available for Sanctuary review."
            ),
            code=TARGET_NOT_AVAILABLE,
        )

    # The author of the target does not need visitor visibility checks.
    # Normally self-target requests are already rejected above unless an
    # internal caller explicitly enables `allow_self_target`.
    if is_owner:
        return (
            owner_user_id,
            True,
        )

    visibility_target = target

    if _is_comment_target(
        target
    ):
        parent_content = _comment_visibility_target(
            target
        )

        if parent_content is None:
            _raise_access_error(
                message=(
                    "The parent content for this "
                    "Comment is no longer available."
                ),
                code=TARGET_NOT_AVAILABLE,
            )

        # A Comment cannot be submitted when its parent content itself
        # is unavailable, hidden, suspended, or moderated.
        if _is_unavailable_content(
            parent_content
        ):
            _raise_access_error(
                message=(
                    "The content containing this "
                    "Comment is no longer available "
                    "for Sanctuary review."
                ),
                code=TARGET_NOT_AVAILABLE,
            )

        # Comment visibility is inherited from its parent content.
        visibility_target = parent_content

    try:
        can_view = VisibilityPolicy.can_view(
            viewer=user,
            obj=visibility_target,
        )
    except Exception:
        can_view = False

    if not can_view:
        _raise_access_error(
            message=(
                "This content is not available "
                "to your account."
            ),
            code=TARGET_NOT_VISIBLE,
        )

    return (
        owner_user_id,
        False,
    )
    
    
def _validate_messenger_group_target(
    *,
    user,
    target,
) -> tuple[int | None, bool]:
    user_id = _authenticated_user_id(
        user
    )

    if not bool(
        getattr(
            target,
            "is_group",
            False,
        )
    ):
        _raise_access_error(
            message=(
                "Only Messenger groups can be "
                "submitted through this Sanctuary "
                "request type."
            ),
            code=INVALID_GROUP_TARGET,
        )

    if not user_id:
        _raise_access_error(
            message="Authentication is required.",
            code=GROUP_MEMBERSHIP_REQUIRED,
        )

    try:
        is_participant = (
            target.participants
            .filter(
                pk=user_id
            )
            .exists()
        )
    except Exception:
        is_participant = False

    if not is_participant:
        _raise_access_error(
            message=(
                "You must be a current member of "
                "this Messenger group to access "
                "its Sanctuary state."
            ),
            code=GROUP_MEMBERSHIP_REQUIRED,
        )

    try:
        is_manager = bool(
            target.is_group_manager(
                user
            )
        )
    except Exception:
        is_manager = False

    return (
        None,
        is_manager,
    )


def _validate_organization_target(
    *,
    user,
    target,
) -> tuple[int | None, bool]:
    user_id = _authenticated_user_id(
        user
    )

    if not bool(
        getattr(
            target,
            "is_active",
            True,
        )
    ):
        _raise_access_error(
            message=(
                "This organization is no longer "
                "available."
            ),
            code=TARGET_NOT_AVAILABLE,
        )

    if bool(
        getattr(
            target,
            "is_hidden",
            False,
        )
    ):
        _raise_access_error(
            message=(
                "This organization is not "
                "currently available."
            ),
            code=TARGET_NOT_AVAILABLE,
        )

    manager_user_ids = (
        _organization_owner_user_ids(
            target
        )
    )

    is_owner = bool(
        user_id
        and user_id in manager_user_ids
    )

    # Organization owners/admins are intentionally allowed to submit
    # a Sanctuary request. Internal misconduct may need escalation.
    return (
        None,
        is_owner,
    )


def assert_sanctuary_target_access(
    *,
    user,
    request_type: str,
    content_type: ContentType,
    object_id: int,
    allow_self_target: bool = False,
) -> SanctuaryTargetAccessResult:
    """
    Central Sanctuary target access policy.

    Boundary is intentionally not used as a rejection condition.
    Sanctuary is a safety mechanism and must remain usable after a
    protective Boundary action.
    """

    normalized_request_type = str(
        request_type or ""
    ).strip()

    if not is_allowed_target_model(
        request_type=normalized_request_type,
        content_type=content_type,
    ):
        _raise_access_error(
            message=(
                "This target model is not allowed "
                "for the selected Sanctuary "
                "request type."
            ),
            code=INVALID_TARGET_MODEL,
            field="content_type",
        )

    target = get_target_object(
        content_type=content_type,
        object_id=object_id,
    )

    if target is None:
        _raise_access_error(
            message="Target object not found.",
            code=TARGET_NOT_FOUND,
            field="object_id",
        )

    if normalized_request_type == "account":
        owner_user_id, is_owner = (
            _validate_account_target(
                user=user,
                target=target,
                allow_self_target=allow_self_target,
            )
        )

    elif normalized_request_type == "content":
        owner_user_id, is_owner = (
            _validate_content_target(
                user=user,
                target=target,
                allow_self_target=allow_self_target,
            )
        )

    elif normalized_request_type == "messenger_group":
        owner_user_id, is_owner = (
            _validate_messenger_group_target(
                user=user,
                target=target,
            )
        )

    elif normalized_request_type == "organization":
        owner_user_id, is_owner = (
            _validate_organization_target(
                user=user,
                target=target,
            )
        )

    else:
        _raise_access_error(
            message="Invalid Sanctuary request type.",
            code=INVALID_TARGET_MODEL,
            field="request_type",
        )

    return SanctuaryTargetAccessResult(
        target=target,
        content_type=content_type,
        content_type_key=content_type_key(
            content_type
        ),
        object_id=int(
            object_id
        ),
        owner_user_id=owner_user_id,
        is_owner=is_owner,
    )