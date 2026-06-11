# apps/core/streams/registry.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Type

from django.db import models


@dataclass(frozen=True)
class StreamContentSource:
    """
    Declarative contract for stream-eligible content.
    """

    model: Type[models.Model]
    kind: str
    media_fields: list[str]
    requires_conversion: bool = True

    # Optional owner lookup for future cross-model owner filtering.
    owner_user_lookup: Optional[str] = None

    # Optional feature flags.
    supports_profile_scope: bool = True
    supports_square_scope: bool = True
    supports_global_scope: bool = True
    supports_owner_scope: bool = True


_STREAM_REGISTRY: dict[str, StreamContentSource] = {}


def register_stream_source(*, source: StreamContentSource) -> None:
    """
    Register a stream source.
    """

    if source.kind in _STREAM_REGISTRY:
        raise RuntimeError(
            f"Stream content kind '{source.kind}' is already registered."
        )

    _STREAM_REGISTRY[source.kind] = source


def get_stream_source(kind: str) -> StreamContentSource | None:
    """
    Get one stream source.
    """

    return _STREAM_REGISTRY.get(kind)


def get_stream_sources() -> list[StreamContentSource]:
    """
    Get all stream sources.
    """

    return list(_STREAM_REGISTRY.values())


def is_stream_kind_registered(kind: str) -> bool:
    """
    Check whether kind is registered.
    """

    return kind in _STREAM_REGISTRY


