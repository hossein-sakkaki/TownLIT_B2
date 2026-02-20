# apps/asset_delivery/permissions.py

import logging
logger = logging.getLogger(__name__)

def safe_can_view_target(request, target_obj) -> bool:
    try:
        viewer = getattr(request, "user", None)
        is_auth = bool(viewer and getattr(viewer, "is_authenticated", False))
    except Exception:
        viewer = None
        is_auth = False

    # ------------------------------------------------------------
    # ✅ SPECIAL CASE: CustomUser avatars (do NOT use VisibilityPolicy)
    # ------------------------------------------------------------
    try:
        from apps.accounts.models import CustomUser
        if isinstance(target_obj, CustomUser):
            # 1) owner can always view
            if is_auth and target_obj.pk == getattr(viewer, "pk", None):
                return True

            # 2) basic moderation gates
            if getattr(target_obj, "is_deleted", False) or getattr(target_obj, "is_suspended", False):
                return False

            # 3) require login
            if not is_auth:
                return False

            # 4) any authenticated user can view avatar
            return True
    except Exception:
        pass


    # ------------------------------------------------------------
    # ✅ SPECIAL CASE: Dialogue (group avatars)
    # Only group members can see group image
    # ------------------------------------------------------------
    try:
        from apps.conversation.models import Dialogue
        if isinstance(target_obj, Dialogue):
            if not is_auth:
                return False

            # allow only participants of the dialogue
            return target_obj.participants.filter(pk=getattr(viewer, "pk", None)).exists()
    except Exception:
        pass


    # ------------------------------------------------------------
    # Apply VisibilityPolicy only to content objects
    # ------------------------------------------------------------
    try:
        if hasattr(target_obj, "visibility") and hasattr(target_obj, "content_object"):
            from apps.core.visibility.policy import VisibilityPolicy
            reason = VisibilityPolicy.gate_reason(viewer=viewer, obj=target_obj)
            return reason is None
    except Exception:
        pass


    # Staff always allowed
    try:
        if is_auth and (getattr(viewer, "is_staff", False) or getattr(viewer, "is_superuser", False)):
            return True
    except Exception:
        pass


    # Owner-like fallbacks
    try:
        owner_user = getattr(target_obj, "user", None)
        if owner_user and is_auth and owner_user.pk == getattr(viewer, "pk", None):
            return True

        owner_member = getattr(target_obj, "owner_member", None)
        if owner_member and is_auth and getattr(owner_member, "pk", None) == getattr(viewer, "pk", None):
            return True

        if hasattr(target_obj, "content_object"):
            owner = getattr(target_obj, "content_object", None)
            if owner and is_auth and getattr(owner, "pk", None) == getattr(viewer, "pk", None):
                return True
    except Exception:
        pass

    return False
