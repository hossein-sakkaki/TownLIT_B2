# validators/mediaValidators/ugc_policies.py

from dataclasses import dataclass
from typing import List, Optional


# -------------------------------------------------
# Shared
# -------------------------------------------------

# Original video upload allowance.
UGC_UPLOAD_MB_PER_MINUTE = 200


# -------------------------------------------------
# Images
# -------------------------------------------------

MOMENT_MAX_IMAGES = 7
MOMENT_IMAGE_MAX_MB = 20
MOMENT_IMAGE_TOTAL_MAX_MB = (
    MOMENT_MAX_IMAGES * MOMENT_IMAGE_MAX_MB
)


@dataclass(frozen=True)
class ImagePolicy:
    min_files: int
    max_files: int
    max_file_mb: int

    def max_total_mb(
        self,
        file_count: int,
    ) -> int:
        if file_count <= 0:
            return 0

        return (
            min(file_count, self.max_files)
            * self.max_file_mb
        )


MOMENT_IMAGE_POLICY = ImagePolicy(
    min_files=1,
    max_files=MOMENT_MAX_IMAGES,
    max_file_mb=MOMENT_IMAGE_MAX_MB,
)


# -------------------------------------------------
# Videos
# -------------------------------------------------

@dataclass(frozen=True)
class VideoTier:
    """
    Tiered original upload size rule.
    """
    max_duration_sec: int
    cap_mb: int
    mb_per_minute: int


@dataclass(frozen=True)
class VideoPolicy:
    min_duration_sec: int
    max_duration_sec: int

    min_fps: Optional[int] = None
    max_fps: Optional[int] = None

    # Kept for backward compatibility.
    tiers: Optional[List["VideoTier"]] = None

    cap_mb: Optional[int] = None
    mb_per_minute: Optional[int] = None


def _round_1(
    value: float,
) -> float:
    """
    Round to 0.1 MB.
    """
    return round(value * 10) / 10


def compute_max_allowed_mb(
    duration_sec: float,
    policy: VideoPolicy,
) -> float:
    """
    Compute maximum original upload size.
    """
    if duration_sec <= 0:
        return 0.0

    minutes = float(duration_sec) / 60.0

    if policy.tiers:
        for tier in policy.tiers:
            if duration_sec <= tier.max_duration_sec:
                by_duration = (
                    tier.mb_per_minute * minutes
                )

                return _round_1(
                    min(
                        float(tier.cap_mb),
                        float(by_duration),
                    )
                )

        return 0.0

    if (
        policy.cap_mb is None
        or policy.mb_per_minute is None
    ):
        return 0.0

    by_duration = (
        policy.mb_per_minute * minutes
    )

    return _round_1(
        min(
            float(policy.cap_mb),
            float(by_duration),
        )
    )


# -------------------------------------------------
# Moments
# 30 sec – 5 minutes
# -------------------------------------------------

MOMENT_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=15,
    max_duration_sec=300,

    min_fps=24,
    max_fps=120,

    cap_mb=1000,
    mb_per_minute=UGC_UPLOAD_MB_PER_MINUTE,
)


# -------------------------------------------------
# Prayers
# 30 sec – 5 minutes
# -------------------------------------------------

PRAYER_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=30,
    max_duration_sec=300,

    min_fps=24,
    max_fps=120,

    cap_mb=1000,
    mb_per_minute=UGC_UPLOAD_MB_PER_MINUTE,
)


# -------------------------------------------------
# Testimonies
# 2 – 10 minutes
# -------------------------------------------------

TESTIMONY_VIDEO_POLICY = VideoPolicy(
    min_duration_sec=120,
    max_duration_sec=600,

    min_fps=24,
    max_fps=120,

    cap_mb=2000,
    mb_per_minute=UGC_UPLOAD_MB_PER_MINUTE,
)