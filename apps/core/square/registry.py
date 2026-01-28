# apps/core/square/registry.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Type, Dict, List, Optional

from django.db import models


@dataclass(frozen=True)
class SquareContentSource:
    """
    Declarative contract for Square-eligible content.

    Backward-compatible:
    - New fields must have defaults so old registrations don't break.
    """
    model: Type[models.Model]
    kind: str                     # moment / testimony / pray
    media_fields: List[str]       # ["video"] or ["image", "video"]
    requires_conversion: bool     # True if availability depends on conversion

    # Optional: how to reach CustomUser id from this model (for friends tab)
    # Example: "owner__user_id" or "owner__custom_user_id"
    owner_user_lookup: Optional[str] = None


# ------------------------------------------------------------------
# Internal registry (singleton)
# ------------------------------------------------------------------

_SQUARE_REGISTRY: Dict[str, SquareContentSource] = {}


# ------------------------------------------------------------------
# Registration API
# ------------------------------------------------------------------

def register_square_source(*, source: SquareContentSource) -> None:
    if source.kind in _SQUARE_REGISTRY:
        raise RuntimeError(
            f"Square content kind '{source.kind}' already registered"
        )

    _SQUARE_REGISTRY[source.kind] = source


def get_square_sources() -> List[SquareContentSource]:
    return list(_SQUARE_REGISTRY.values())


def get_square_source(kind: str) -> SquareContentSource | None:
    return _SQUARE_REGISTRY.get(kind)
