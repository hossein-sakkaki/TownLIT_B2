# apps/core/square/stream/constants.py

# ----------------------------------
# Stream content subtypes (universal)
# ----------------------------------
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

# ----------------------------------
# Anti-addiction limits
# ----------------------------------
STREAM_PAGE_SIZE = 5          # items per scroll
STREAM_MAX_EXTENSIONS = 3     # number of "continue?" accepts
STREAM_MAX_ITEMS = STREAM_PAGE_SIZE * STREAM_MAX_EXTENSIONS
