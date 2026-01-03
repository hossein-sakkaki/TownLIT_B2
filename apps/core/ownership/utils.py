# apps/core/ownership/utils.py

def resolve_owner_from_request(request):
    user = request.user
    if not user or not user.is_authenticated:
        return None

    return (
        getattr(user, "member_profile", None)
        or getattr(user, "guest_profile", None)
    )
