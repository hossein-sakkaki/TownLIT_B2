# apps/ai_gateway/registry.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""Code-reviewed metadata registry. There are no callable domain handlers."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Operation:
    name: str
    version: int
    scope: str
    allowed_agents: frozenset[str]


OPERATIONS = MappingProxyType({
    ("gateway.capabilities", 1): Operation(
        "gateway.capabilities", 1, "gateway.metadata",
        frozenset({"phoebe", "silas", "micah"}),
    ),
})
