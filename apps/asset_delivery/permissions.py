# apps/asset_delivery/permissions.py

import logging

logger = logging.getLogger(__name__)


def safe_can_view_target(request, target_obj) -> bool:
    """
    Best-effort visibility gate.
    Never raise.
    """
    # 1) VisibilityPolicy (preferred)
    try:
        from apps.core.visibility.policy import VisibilityPolicy
        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=target_obj)
        return reason is None
    except Exception:
        pass

    # 2) Staff always allowed
    try:
        if getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False):
            return True
    except Exception:
        pass

    # 3) Owner-like fallbacks
    try:
        owner_user = getattr(target_obj, "user", None)
        if owner_user and owner_user.pk == getattr(request.user, "pk", None):
            return True

        owner_member = getattr(target_obj, "owner_member", None)
        if owner_member and getattr(owner_member, "pk", None) == getattr(request.user, "pk", None):
            return True

        # Generic fallback
        if hasattr(target_obj, "content_object"):
            owner = getattr(target_obj, "content_object", None)
            if owner and getattr(owner, "pk", None) == getattr(request.user, "pk", None):
                return True
    except Exception:
        pass

    return False
