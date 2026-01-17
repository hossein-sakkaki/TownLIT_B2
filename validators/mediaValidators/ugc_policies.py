# apps/media_conversion/services/ugc_policies.py
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class VideoTier:
    """
    Tiered policy rule:
    - applies when durationSec <= max_duration_sec
    - max allowed size = min(cap_mb, mb_per_minute * duration_minutes)
    """
    max_duration_sec: int
    cap_mb: int
    mb_per_minute: int


@dataclass(frozen=True)
class VideoPolicy:
    # Duration rules
    min_duration_sec: int
    max_duration_sec: int

    # FPS rules (NEW – backward compatible)
    min_fps: Optional[int] = None
    max_fps: Optional[int] = None

    # Tiered size rules
    tiers: Optional[List["VideoTier"]] = None

    # Default size rules (when tiers is None)
    cap_mb: Optional[int] = None
    mb_per_minute: Optional[int] = None


def _round_1(x: float) -> float:
    return round(x * 10) / 10


def compute_max_allowed_mb(duration_sec: float, policy: VideoPolicy) -> float:
    """
    Compute max allowed MB based on duration + policy.
    """
    if duration_sec <= 0:
        return 0.0

    minutes = float(duration_sec) / 60.0

    # Tiered policy
    if policy.tiers:
        for tier in policy.tiers:
            if duration_sec <= tier.max_duration_sec:
                by_duration = tier.mb_per_minute * minutes
                return _round_1(min(float(tier.cap_mb), float(by_duration)))

        # duration exceeds the last tier max -> treat as too long at policy level
        return 0.0

    # Non-tier policy
    if policy.cap_mb is None or policy.mb_per_minute is None:
        return 0.0

    by_duration = policy.mb_per_minute * minutes
    return _round_1(min(float(policy.cap_mb), float(by_duration)))


# -------------------------------------------------
# Moments
# Min: 60s  Max: 180s
# Max size: min(210MB, 70MB * duration_minutes)
# -------------------------------------------------
MOMENT_VIDEO_POLICY = VideoPolicy(
    # Duration: short-form content
    min_duration_sec=5,
    max_duration_sec=180,

    # FPS: mobile-friendly, CPU-safe
    min_fps=24,
    max_fps=120,

    # Size: dynamic cap
    cap_mb=200,
    mb_per_minute=60,
)



# -------------------------------------------------
# Testimonies (Video)
# Min: 120s  Max: 600s
# tiers:
#  2–6 min  : cap 500MB, 85MB/min
#  6–10 min : cap 700MB, 70MB/min
# -------------------------------------------------
TESTIMONY_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=120,
    max_duration_sec=600,
    tiers=[
        VideoTier(max_duration_sec=360, cap_mb=500, mb_per_minute=85),
        VideoTier(max_duration_sec=600, cap_mb=700, mb_per_minute=70),
    ],
)
