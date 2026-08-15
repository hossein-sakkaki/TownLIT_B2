# apps/content_safety/services/types.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LocalSafetySignals:
    suspicious: bool

    profanity: bool = False
    abusive_language: bool = False
    sexual_solicitation: bool = False
    spam: bool = False
    scam: bool = False

    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderModerationResult:
    flagged: bool

    categories: dict[str, bool]
    category_scores: dict[str, float]
    applied_input_types: dict[str, list[str]]

    provider: str
    model: str
    response_id: str = ""

    cached: bool = False


@dataclass(frozen=True)
class SafetyPolicyResult:
    decision: str
    risk_level: str
    reason_code: str

    requires_adjudication: bool = False


@dataclass(frozen=True)
class TextSafetyResult:
    decision: str
    risk_level: str
    reason_code: str

    input_hash: str

    provider: str = ""
    provider_model: str = ""
    provider_flagged: bool = False

    categories: dict[str, bool] = field(
        default_factory=dict
    )

    category_scores: dict[str, float] = field(
        default_factory=dict
    )

    local_signals: tuple[str, ...] = ()

    cached: bool = False

    adjudicated: bool = False
    adjudication_model: str = ""
    adjudication_cached: bool = False

    @property
    def is_allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def is_blocked(self) -> bool:
        return self.decision == "block"

    @property
    def requires_review(self) -> bool:
        return self.decision == "review"