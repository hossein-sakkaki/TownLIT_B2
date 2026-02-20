# apps/core/square/projections/registry.py

from typing import Dict, Type
from .base import SquareProjection

PROJECTION_REGISTRY: Dict[str, Type[SquareProjection]] = {}


def register_projection(kind: str):
    """
    Decorator to register projection class.
    """
    def wrapper(cls: Type[SquareProjection]):
        PROJECTION_REGISTRY[kind] = cls
        cls.kind = kind
        return cls
    return wrapper


def get_projection(kind: str):
    return PROJECTION_REGISTRY.get(kind)
