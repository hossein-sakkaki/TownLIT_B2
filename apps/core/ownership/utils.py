# apps/core/ownership/utils.py

from apps.profiles.services.active_profile import get_active_profile


def resolve_owner_from_request(request):
    """Resolve the active owner profile from request user."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    active = get_active_profile(user)
    return active.profile