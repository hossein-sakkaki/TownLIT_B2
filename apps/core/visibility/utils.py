# apps/core/visibility/utils.py

def is_owner(viewer, obj) -> bool:
    try:
        owner = obj.content_object
        if hasattr(owner, "user"):
            return owner.user_id == getattr(viewer, "id", None)
        return owner.id == getattr(viewer, "id", None)
    except Exception:
        return False
