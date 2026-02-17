# apps/media_conversion/services/ugc_policies.py
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class VideoTier:
    """
    Tiered size rule:
    max size = min(cap_mb, mb_per_minute * duration_minutes)
    Applied when duration_sec <= max_duration_sec
    """
    max_duration_sec: int
    cap_mb: int
    mb_per_minute: int


@dataclass(frozen=True)
class VideoPolicy:
    # Duration rules (DO NOT change lightly)
    min_duration_sec: int
    max_duration_sec: int

    # FPS guardrails (soft limits)
    min_fps: Optional[int] = None
    max_fps: Optional[int] = None

    # Tiered size rules (preferred)
    tiers: Optional[List["VideoTier"]] = None

    # Fallback size rules (used if tiers is None)
    cap_mb: Optional[int] = None
    mb_per_minute: Optional[int] = None


def _round_1(x: float) -> float:
    """Round to 1 decimal place for stable UI/UX."""
    return round(x * 10) / 10


def compute_max_allowed_mb(duration_sec: float, policy: VideoPolicy) -> float:
    """
    Compute max allowed upload size (MB)
    based on duration and policy.
    """
    if duration_sec <= 0:
        return 0.0

    minutes = float(duration_sec) / 60.0

    # Tiered policy (preferred)
    if policy.tiers:
        for tier in policy.tiers:
            if duration_sec <= tier.max_duration_sec:
                by_duration = tier.mb_per_minute * minutes
                return _round_1(min(float(tier.cap_mb), float(by_duration)))

        # Duration exceeds last tier -> reject at policy level
        return 0.0

    # Non-tier fallback
    if policy.cap_mb is None or policy.mb_per_minute is None:
        return 0.0

    by_duration = policy.mb_per_minute * minutes
    return _round_1(min(float(policy.cap_mb), float(by_duration)))


# -------------------------------------------------
# Moments (Video)
# Duration unchanged
# Size relaxed for modern high-quality mobile videos
# -------------------------------------------------
MOMENT_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=60,
    max_duration_sec=180,

    # Accept wide mobile FPS range
    min_fps=24,
    max_fps=120,

    # Higher bitrate tolerance
    cap_mb=300,
    mb_per_minute=90,
)


# -------------------------------------------------
# Testimonies (Video – tiered)
# Duration unchanged
# Designed for high-quality 1080p recordings
# -------------------------------------------------
TESTIMONY_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=120,
    max_duration_sec=600,

    tiers=[
        # 2–6 min: very high quality allowed
        VideoTier(
            max_duration_sec=360,
            cap_mb=650,
            mb_per_minute=110,
        ),

        # 6–10 min: high quality, controlled growth
        VideoTier(
            max_duration_sec=600,
            cap_mb=950,
            mb_per_minute=95,
        ),
    ],
)
