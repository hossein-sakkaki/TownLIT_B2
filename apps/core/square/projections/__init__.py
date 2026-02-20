# apps/core/square/projections/__init__.py

"""
Force import projection modules so decorators register themselves.
This runs at Django startup.
"""

from .moment import MomentSquareProjection  # noqa: F401
from .testimony import TestimonySquareProjection  # noqa: F401
