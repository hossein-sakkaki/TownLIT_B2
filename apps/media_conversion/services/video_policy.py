# apps/media_conversion/services/video_policy.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


VideoRenditionMode = Literal["single", "multi"]


@dataclass(frozen=True)
class VideoRenditionPolicy:
    """
    Central video rendition policy.

    mode:
    - multi: adaptive HLS renditions
    - single: one high-quality HLS rendition

    max_height:
    - Caps very large uploads to avoid huge storage/CPU cost.
    """
    mode: VideoRenditionMode
    max_height: int = 1080


# ---------------------------------------------------------------------
# Policy table
# ---------------------------------------------------------------------

VIDEO_RENDITION_POLICIES: dict[tuple[str, str, str], VideoRenditionPolicy] = {
    # Main long-form / durable content.
    ("posts", "testimony", "video"): VideoRenditionPolicy(
        mode="multi",
        max_height=1080,
    ),

    # Short / frequent content.
    ("posts", "moment", "video"): VideoRenditionPolicy(
        mode="single",
        max_height=1080,
    ),

    ("posts", "prayer", "video"): VideoRenditionPolicy(
        mode="single",
        max_height=1080,
    ),

    ("posts", "prayerresponse", "video"): VideoRenditionPolicy(
        mode="single",
        max_height=1080,
    ),
}


DEFAULT_VIDEO_RENDITION_POLICY = VideoRenditionPolicy(
    mode="single",
    max_height=1080,
)


def get_video_rendition_policy(
    *,
    app_label: str,
    model_name: str,
    field_name: str,
) -> VideoRenditionPolicy:
    """
    Resolve video rendition policy by app/model/field.
    """
    key = (
        str(app_label or "").lower(),
        str(model_name or "").lower(),
        str(field_name or "").lower(),
    )

    return VIDEO_RENDITION_POLICIES.get(
        key,
        DEFAULT_VIDEO_RENDITION_POLICY,
    )


def get_video_rendition_policy_for_instance(
    instance,
    *,
    field_name: str,
) -> VideoRenditionPolicy:
    """
    Resolve video rendition policy from a Django model instance.
    """
    meta = getattr(instance, "_meta", None)

    app_label = getattr(meta, "app_label", "") or ""
    model_name = getattr(meta, "model_name", "") or ""

    return get_video_rendition_policy(
        app_label=app_label,
        model_name=model_name,
        field_name=field_name,
    )