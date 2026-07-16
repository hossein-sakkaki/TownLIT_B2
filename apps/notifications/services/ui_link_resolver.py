# apps/notifications/services/ui_link_resolver.py

from urllib.parse import urlencode

# ------------------------------------------------------------
# Content entry map (API roots for retrieve-by-slug)
# ------------------------------------------------------------
ENTRY_BY_CT = {
    # posts
    "posts.moment": "/posts/moments",
    "posts.testimony": "/posts/testimonies",
    "posts.prayer": "/posts/prayers",
    # add more later...
}

# ------------------------------------------------------------
# Legacy aliases (keep old notifications working)
# ------------------------------------------------------------
LEGACY_ENTRY_ALIASES = {
    "/posts/me/testimonies": "/posts/testimonies",
    "/posts/me/moments": "/posts/moments",
}


def normalize_entry_section(section: str) -> str:
    """Normalize old/alias entry paths to valid API roots."""
    if not section:
        return "/posts"

    s = section.strip()

    if not s.startswith("/"):
        s = f"/{s}"

    return LEGACY_ENTRY_ALIASES.get(s, s)


def guess_entry_section(ct_key: str) -> str:
    """Return entry section for 'e' param."""
    return ENTRY_BY_CT.get(ct_key, "/posts")


def build_content_link(
    *,
    slug: str,
    section: str,
    focus: str | None = None,
    mode: str = "read",
    owner_username: str | None = None,
    key_path: str | None = None,
    extra_params: dict | None = None,
) -> str:
    """
    Build frontend-safe deep-link for universal content pages.

    Notes:
    - Web uses /content/<slug> directly.
    - iOS uses extra query hints to open the same content through the
      profile-scoped stream viewer.
    - Extra params are non-breaking for web.
    """
    params = {
        "type": mode,
        "e": normalize_entry_section(section),
    }

    if focus:
        params["focus"] = focus

    if owner_username:
        params["u"] = owner_username

    if key_path:
        params["k"] = key_path

    if isinstance(extra_params, dict):
        for key, value in extra_params.items():
            if value is None:
                continue

            params[str(key)] = str(value)

    return f"/content/{slug}?{urlencode(params)}"

# ------------------------------------------------------------
# Profile / action links
# ------------------------------------------------------------

def build_member_profile_link(
    *,
    username: str | None = None,
) -> str:
    """
    Safe frontend profile link.

    Website/iOS can route this to the authenticated user's profile.
    """
    if username:
        return f"/profiles/members/profile?u={username}"

    return "/profiles/members/profile"


def build_testimony_create_link(
    *,
    username: str | None = None,
    kind: str = "video",
    source: str = "notification",
) -> str:
    """
    Best-effort creation intent link.

    If frontend/iOS supports query intent, it can open testimony creation.
    If not, this still lands on profile safely.
    """
    params = {
        "create": "testimony",
        "kind": kind,
        "source": source,
    }

    if username:
        params["u"] = username

    return f"/profiles/members/profile?{urlencode(params)}"

# ------------------------------------------------------------
# Friendships
# ------------------------------------------------------------
def build_friendship_request_link(
    *,
    friendship_id: int,
    user_id: int | None = None,
    username: str | None = None,
    request_kind: str = "received",
) -> str:
    """
    Build a precise friendship request deep link.
    """
    params = {
        "tab": "requests",
        "request_id": friendship_id,
        "friendship_id": friendship_id,
        "request_kind": request_kind,
    }

    if user_id is not None:
        params["user_id"] = user_id

    if username:
        cleaned_username = str(username).strip()

        if cleaned_username:
            params["username"] = cleaned_username

    return (
        "/settings/friendships?"
        f"{urlencode(params)}"
    )