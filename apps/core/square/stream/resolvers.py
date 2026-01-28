# apps/core/square/stream/resolvers.py

from apps.core.square.stream.constants import (
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_IMAGE,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_WRITTEN,
)

from apps.posts.models.testimony import Testimony
from apps.posts.models.moment import Moment


def resolve_stream_subtype(obj) -> str | None:
    """
    Central subtype resolver.
    Extend this when new models are added.
    """

    # -----------------------------
    # Testimony
    # -----------------------------
    if isinstance(obj, Testimony):
        if obj.type == Testimony.TYPE_VIDEO:
            return STREAM_SUBTYPE_VIDEO
        if obj.type == Testimony.TYPE_AUDIO:
            return STREAM_SUBTYPE_AUDIO
        if obj.type == Testimony.TYPE_WRITTEN:
            return STREAM_SUBTYPE_WRITTEN

    # -----------------------------
    # Moment
    # -----------------------------
    if isinstance(obj, Moment):
        if obj.video:
            return STREAM_SUBTYPE_VIDEO
        if obj.image:
            return STREAM_SUBTYPE_IMAGE

    return None
