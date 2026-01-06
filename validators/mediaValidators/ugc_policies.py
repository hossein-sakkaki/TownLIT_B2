from dataclasses import dataclass
from typing import List, Optional
from math import ceil


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
    min_duration_sec: int
    max_duration_sec: int

    # If tiers provided, they override cap_mb/mb_per_minute
    tiers: Optional[List[VideoTier]] = None

    # Default non-tier policy (used when tiers is None)
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
    min_duration_sec=60,
    max_duration_sec=180,
    cap_mb=210,
    mb_per_minute=70,
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
