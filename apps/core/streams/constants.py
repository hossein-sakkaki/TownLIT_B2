# apps/core/streams/constants.py

# =====================================================
# Stream scopes
# =====================================================

STREAM_SCOPE_SQUARE = "square"
STREAM_SCOPE_PROFILE = "profile"
STREAM_SCOPE_OWNER = "owner"
STREAM_SCOPE_GLOBAL = "global"

STREAM_SCOPES = {
    STREAM_SCOPE_SQUARE,
    STREAM_SCOPE_PROFILE,
    STREAM_SCOPE_OWNER,
    STREAM_SCOPE_GLOBAL,
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

STREAM_PAGE_SIZE = 5
STREAM_MAX_EXTENSIONS = 3
STREAM_MAX_ITEMS = STREAM_PAGE_SIZE * STREAM_MAX_EXTENSIONS


# =====================================================
# Testimony fallback
# =====================================================

TESTIMONY_FALLBACK_SUBTYPES = [
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_WRITTEN,
]