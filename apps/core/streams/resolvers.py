# apps/core/streams/resolvers.py

from apps.core.streams.constants import (
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_IMAGE,
    STREAM_SUBTYPE_WRITTEN,
)

from apps.posts.models.testimony import Testimony
from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer


def _has_moment_images(obj: Moment) -> bool:
    """
    Detect legacy and JSON-backed photo Moments.
    """
    if getattr(obj, "image", None):
        return True

    try:
        if hasattr(obj, "normalized_image_items"):
            return bool(obj.normalized_image_items())
    except Exception:
        pass

    image_items = getattr(obj, "image_items", None)
    return bool(image_items)


def resolve_stream_subtype(obj) -> str | None:
    """
    Resolve subtype for stream object.
    """

    if isinstance(obj, Testimony):
        if obj.type == Testimony.TYPE_VIDEO:
            return STREAM_SUBTYPE_VIDEO
        if obj.type == Testimony.TYPE_AUDIO:
            return STREAM_SUBTYPE_AUDIO
        if obj.type == Testimony.TYPE_WRITTEN:
            return STREAM_SUBTYPE_WRITTEN

    if isinstance(obj, Moment):
        if obj.video:
            return STREAM_SUBTYPE_VIDEO
        if _has_moment_images(obj):
            return STREAM_SUBTYPE_IMAGE

    if isinstance(obj, Prayer):
        if obj.video:
            return STREAM_SUBTYPE_VIDEO
        if obj.image:
            return STREAM_SUBTYPE_IMAGE

    return None