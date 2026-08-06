# apps/asset_delivery/permissions.py

import logging

logger = logging.getLogger(__name__)


def _extract_owner_user_id(obj):
    """Best-effort owner resolver."""
    if obj is None:
        return None

    try:
        if getattr(obj, "user_id", None):
            return obj.user_id

        user = getattr(obj, "user", None)

        if user is not None and hasattr(user, "pk"):
            return user.pk
    except Exception:
        pass

    try:
        owner = getattr(obj, "content_object", None)

        if owner is not None:
            if getattr(owner, "user_id", None):
                return owner.user_id

            owner_user = getattr(owner, "user", None)

            if owner_user is not None and hasattr(owner_user, "pk"):
                return owner_user.pk
    except Exception:
        pass

    for attr in (
        "owner",
        "created_by",
        "author",
    ):
        try:
            owner = getattr(obj, attr, None)

            if owner is None:
                continue

            if getattr(owner, "user_id", None):
                return owner.user_id

            owner_user = getattr(owner, "user", None)

            if owner_user is not None and hasattr(owner_user, "pk"):
                return owner_user.pk

            if hasattr(owner, "pk"):
                return owner.pk
        except Exception:
            continue

    return None


def _iter_parent_candidates(obj):
    """Yield likely parent objects."""
    if obj is None:
        return

    for attr in (
        "parent",
        "post",
        "moment",
        "prayer",
        "target",
        "source",
    ):
        try:
            parent = getattr(obj, attr, None)

            if parent is not None:
                yield parent
        except Exception:
            continue


def safe_can_deliver_public_user_avatar(
    target_obj,
    *,
    field_name: str,
) -> bool:
    """
    Allow delivery of a visible user's avatar without exposing other
    CustomUser assets or enabling anonymous profile access.

    The playback gateway resolves the public alias `avatar` to the
    canonical CustomUser field `image_name` before permission checks.
    Accept both values so direct and normalized callers follow the
    same restricted avatar-only policy.
    """
    try:
        from apps.accounts.models.user import CustomUser
    except Exception:
        logger.exception(
            "asset_delivery.custom_user import failed"
        )
        return False

    if not isinstance(
        target_obj,
        CustomUser,
    ):
        return False

    normalized_field_name = str(
        field_name or ""
    ).strip().lower()

    if normalized_field_name not in {
        "avatar",
        "image_name",
    }:
        return False

    if getattr(
        target_obj,
        "is_deleted",
        False,
    ):
        return False

    if getattr(
        target_obj,
        "is_suspended",
        False,
    ):
        return False

    return True

def safe_can_view_target(
    request,
    target_obj,
) -> bool:
    try:
        viewer = getattr(
            request,
            "user",
            None,
        )

        is_auth = bool(
            viewer and
            getattr(
                viewer,
                "is_authenticated",
                False,
            )
        )
    except Exception:
        viewer = None
        is_auth = False

    # CustomUser access outside the field-aware avatar gateway.
    try:
        from apps.accounts.models.user import CustomUser

        if isinstance(
            target_obj,
            CustomUser,
        ):
            if (
                is_auth and
                target_obj.pk ==
                getattr(
                    viewer,
                    "pk",
                    None,
                )
            ):
                return True

            if (
                getattr(
                    target_obj,
                    "is_deleted",
                    False,
                ) or
                getattr(
                    target_obj,
                    "is_suspended",
                    False,
                )
            ):
                return False

            if not is_auth:
                return False

            return True
    except Exception:
        pass

    # Group avatars remain participant-only.
    try:
        from apps.conversation.models import Dialogue

        if isinstance(
            target_obj,
            Dialogue,
        ):
            if not is_auth:
                return False

            return target_obj.participants.filter(
                pk=getattr(
                    viewer,
                    "pk",
                    None,
                )
            ).exists()
    except Exception:
        pass

    # Apply visibility policy to content objects.
    try:
        if hasattr(
            target_obj,
            "visibility",
        ):
            from apps.core.visibility.policy import VisibilityPolicy

            reason = VisibilityPolicy.gate_reason(
                viewer=viewer,
                obj=target_obj,
            )

            return reason is None
    except Exception:
        pass

    try:
        if is_auth and (
            getattr(
                viewer,
                "is_admin",
                False,
            ) or
            getattr(
                viewer,
                "is_superuser",
                False,
            ) or
            getattr(
                viewer,
                "is_staff",
                False,
            )
        ):
            return True
    except Exception:
        pass

    try:
        owner_user = getattr(
            target_obj,
            "user",
            None,
        )

        if (
            owner_user and
            is_auth and
            owner_user.pk ==
            getattr(
                viewer,
                "pk",
                None,
            )
        ):
            return True

        owner_member = getattr(
            target_obj,
            "owner_member",
            None,
        )

        if (
            owner_member and
            is_auth and
            getattr(
                owner_member,
                "pk",
                None,
            ) ==
            getattr(
                viewer,
                "pk",
                None,
            )
        ):
            return True

        if hasattr(
            target_obj,
            "content_object",
        ):
            owner = getattr(
                target_obj,
                "content_object",
                None,
            )

            if (
                owner and
                is_auth and
                getattr(
                    owner,
                    "pk",
                    None,
                ) ==
                getattr(
                    viewer,
                    "pk",
                    None,
                )
            ):
                return True
    except Exception:
        pass

    try:
        owner_user_id = _extract_owner_user_id(
            target_obj
        )

        if (
            owner_user_id and
            is_auth and
            owner_user_id ==
            getattr(
                viewer,
                "pk",
                None,
            )
        ):
            return True

        for parent in _iter_parent_candidates(
            target_obj
        ):
            try:
                if hasattr(
                    parent,
                    "visibility",
                ):
                    from apps.core.visibility.policy import VisibilityPolicy

                    reason = VisibilityPolicy.gate_reason(
                        viewer=viewer,
                        obj=parent,
                    )

                    if reason is None:
                        return True
            except Exception:
                pass

            owner_user_id = _extract_owner_user_id(
                parent
            )

            if (
                owner_user_id and
                is_auth and
                owner_user_id ==
                getattr(
                    viewer,
                    "pk",
                    None,
                )
            ):
                return True
    except Exception:
        pass

    return False