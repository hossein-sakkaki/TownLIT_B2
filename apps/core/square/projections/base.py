# apps/core/square/projections/base.py

from __future__ import annotations
from typing import Any, Dict


class SquareProjection:
    """
    Lightweight projection for Square feed items.

    IMPORTANT:
    - NO heavy serialization
    - NO media signing
    - NO playback resolving
    - Only lightweight DB fields
    """

    kind: str = "unknown"

    def __init__(self, obj, *, request=None, viewer=None):
        self.obj = obj
        self.request = request
        self.viewer = viewer

    # ---------------------------------------------------------

    def get_preview(self) -> Dict[str, Any]:
        """
        Must return CDN-ready preview URLs.
        """
        raise NotImplementedError

    def get_meta(self) -> Dict[str, Any]:
        """
        Lightweight text metadata.
        """
        return {}

    # ---------------------------------------------------------

    def serialize(self) -> Dict[str, Any] | None:
        """
        Final normalized payload for Square.
        """
        preview = self.get_preview()
        if not preview:
            return None

        return {
            "kind": self.kind,
            "id": self.obj.id,
            "published_at": getattr(self.obj, "published_at", None),
            "preview": preview,
            "meta": self.get_meta(),
        }
