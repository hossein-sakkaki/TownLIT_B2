# apps/core/streams/sources.py

from apps.core.streams.registry import (
    StreamContentSource,
    register_stream_source,
)

from apps.core.streams.constants import (
    STREAM_KIND_MOMENT,
    STREAM_KIND_TESTIMONY,
    STREAM_KIND_PRAY,
)

from apps.posts.models.moment import Moment
from apps.posts.models.testimony import Testimony
from apps.posts.models.pray import Prayer


# -------------------------------------------------
# Moment
# -------------------------------------------------

register_stream_source(
    source=StreamContentSource(
        model=Moment,
        kind=STREAM_KIND_MOMENT,
        media_fields=["video", "image"],
        requires_conversion=True,
        owner_user_lookup="content_type/object_id",
    )
)


# -------------------------------------------------
# Testimony
# -------------------------------------------------

register_stream_source(
    source=StreamContentSource(
        model=Testimony,
        kind=STREAM_KIND_TESTIMONY,
        media_fields=["video", "audio", "written"],
        requires_conversion=True,
        owner_user_lookup="content_type/object_id",
    )
)


# -------------------------------------------------
# Prayer
# -------------------------------------------------

register_stream_source(
    source=StreamContentSource(
        model=Prayer,
        kind=STREAM_KIND_PRAY,
        media_fields=["video", "image"],
        requires_conversion=True,
        owner_user_lookup="content_type/object_id",
    )
)

