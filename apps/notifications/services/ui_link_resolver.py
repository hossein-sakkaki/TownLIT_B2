from urllib.parse import urlencode

# ------------------------------------------------------------
# Content entry map (API roots for retrieve-by-slug)
# ------------------------------------------------------------
ENTRY_BY_CT = {
    # posts
    "posts.moment": "/posts/moments",
    "posts.testimony": "/posts/testimonies",
    # add more later:
    # "posts.pray": "/posts/prays",
    # "posts.post": "/posts/posts",
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
    """Return entry section for 'e' param (safe fallback)."""
    return ENTRY_BY_CT.get(ct_key, "/posts")

def build_content_link(
    *,
    slug: str,
    section: str,
    focus: str | None = None,
    mode: str = "read",
) -> str:
    """
    Build frontend-safe deep-link for universal content pages.
    """
    params = {
        "type": mode,
        "e": normalize_entry_section(section),
    }
    if focus:
        params["focus"] = focus

    return f"/content/{slug}?{urlencode(params)}"
