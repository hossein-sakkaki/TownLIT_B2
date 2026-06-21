# apps/core/streams/constants.py

# =====================================================
# Stream scopes
# =====================================================

STREAM_SCOPE_SQUARE = "square"
STREAM_SCOPE_PROFILE = "profile"
STREAM_SCOPE_OWNER = "owner"
STREAM_SCOPE_GLOBAL = "global"
STREAM_SCOPE_MESSENGER = "messenger"

STREAM_SCOPES = {
    STREAM_SCOPE_SQUARE,
    STREAM_SCOPE_PROFILE,
    STREAM_SCOPE_OWNER,
    STREAM_SCOPE_GLOBAL,
    STREAM_SCOPE_MESSENGER,
}

STREAM_LIMITED_EXTENSION_SCOPES = {
    STREAM_SCOPE_SQUARE,
    STREAM_SCOPE_MESSENGER,
}


# =====================================================
# Stream kinds
# =====================================================

STREAM_KIND_MOMENT = "moment"
STREAM_KIND_TESTIMONY = "testimony"
STREAM_KIND_PRAY = "pray"

STREAM_KINDS = {
    STREAM_KIND_MOMENT,
    STREAM_KIND_TESTIMONY,
    STREAM_KIND_PRAY,
}


# =====================================================
# Stream subtypes
# =====================================================

STREAM_SUBTYPE_VIDEO = "video"
STREAM_SUBTYPE_AUDIO = "audio"
STREAM_SUBTYPE_IMAGE = "image"
STREAM_SUBTYPE_WRITTEN = "written"

STREAM_SUBTYPES = {
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_IMAGE,
    STREAM_SUBTYPE_WRITTEN,
}


# =====================================================
# Stream modes
# =====================================================

STREAM_MODE_RELATED = "related"
STREAM_MODE_RECENT = "recent"

STREAM_MODES = {
    STREAM_MODE_RELATED,
    STREAM_MODE_RECENT,
}


# =====================================================
# Pagination and limits
# =====================================================

# Default stream page size used by non-Square scopes unless overridden.
STREAM_PAGE_SIZE = 7

# Square is intentionally limited to avoid addictive infinite streaming.
# extension=0 => first 7
# extension=1 => second 7
# extension=2 => third 7
# extension>=3 => blocked
STREAM_SQUARE_PAGE_SIZE = 7
STREAM_SQUARE_MAX_EXTENSIONS = 3
STREAM_SQUARE_MAX_ITEMS = STREAM_SQUARE_PAGE_SIZE * STREAM_SQUARE_MAX_EXTENSIONS

# Backward-compatible names.
# Keep these aliases only if other stream modules still import them.
STREAM_MAX_EXTENSIONS = STREAM_SQUARE_MAX_EXTENSIONS
STREAM_MAX_ITEMS = STREAM_SQUARE_MAX_ITEMS


# =====================================================
# Testimony fallback
# =====================================================

TESTIMONY_FALLBACK_SUBTYPES = [
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_WRITTEN,
]