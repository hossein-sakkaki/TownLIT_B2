# apps/media_conversion/services/ugc_policies.py

from dataclasses import dataclass
from typing import List, Optional


# 🔥 Unified bitrate policy
UGC_MB_PER_MINUTE = 120


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
    # Duration rules
    min_duration_sec: int
    max_duration_sec: int

    # FPS guardrails (soft limits)
    min_fps: Optional[int] = None
    max_fps: Optional[int] = None

    # Tiered size rules (not used anymore, but kept for compatibility)
    tiers: Optional[List["VideoTier"]] = None

    # Fallback size rules
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

    # Tiered policy (kept for backward compatibility)
    if policy.tiers:
        for tier in policy.tiers:
            if duration_sec <= tier.max_duration_sec:
                by_duration = tier.mb_per_minute * minutes
                return _round_1(min(float(tier.cap_mb), float(by_duration)))
        return 0.0

    # Standard unified policy
    if policy.cap_mb is None or policy.mb_per_minute is None:
        return 0.0

    by_duration = policy.mb_per_minute * minutes
    return _round_1(min(float(policy.cap_mb), float(by_duration)))


# -------------------------------------------------
# Moments (Video)
# 1–3 minutes
# -------------------------------------------------
MOMENT_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=60,
    max_duration_sec=180,

    min_fps=24,
    max_fps=120,

    cap_mb=360,  # 3 × 120
    mb_per_minute=UGC_MB_PER_MINUTE,
)


# -------------------------------------------------
# Prayers (Video)
# 30 sec – 5 minutes
# -------------------------------------------------
PRAYER_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=30,
    max_duration_sec=300,

    min_fps=24,
    max_fps=120,

    cap_mb=600,  # 5 × 120
    mb_per_minute=UGC_MB_PER_MINUTE,
)


# -------------------------------------------------
# Testimonies (Video)
# 2 – 10 minutes
# -------------------------------------------------
TESTIMONY_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=120,
    max_duration_sec=600,

    min_fps=24,
    max_fps=120,

    cap_mb=1200,  # 10 × 120
    mb_per_minute=UGC_MB_PER_MINUTE,
)