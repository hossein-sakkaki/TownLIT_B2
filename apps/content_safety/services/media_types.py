# apps/content_safety/services/media_types.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImageSafetyResult:
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

    cached: bool = False

    guarded: bool = False
    guard_model: str = ""
    guard_decision: str = ""
    guard_reason_code: str = ""
    guard_cached: bool = False

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


@dataclass(frozen=True)
class VideoSafetyResult:
    decision: str
    risk_level: str
    reason_code: str
    input_hash: str

    duration_ms: int = 0
    frame_count: int = 0

    visual_decision: str = ""
    visual_reason_code: str = ""
    visual_provider_flagged: bool = False

    visual_guarded: bool = False
    visual_guard_model: str = ""

    visual_adjudicated: bool = False
    visual_adjudication_model: str = ""

    has_audio: bool = False

    transcript_present: bool = False
    transcript_hash: str = ""
    transcript_decision: str = ""
    transcript_reason_code: str = ""
    transcript_model: str = ""
    transcript_chunks: int = 0
    transcript_adjudicated: bool = False

    cached: bool = False

    @property
    def is_allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def is_blocked(self) -> bool:
        return self.decision == "block"

    @property
    def requires_review(self) -> bool:
        return self.decision == "review"