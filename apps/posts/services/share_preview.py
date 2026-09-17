# apps/posts/services/share_preview.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-17.
# Last Update by Hossein Sakkaki on 2026-09-17.

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from django.utils import timezone

from apps.core.visibility.constants import (
    VISIBILITY_GLOBAL,
)
from apps.core.visibility.policy import (
    VisibilityPolicy,
)
from apps.posts.constants.journeys import (
    JourneyRetentionPolicy,
)
from apps.posts.models.journey import (
    JourneyEntry,
)
from apps.posts.models.moment import (
    Moment,
)
from apps.posts.models.pray import (
    Prayer,
)
from apps.posts.models.testimony import (
    Testimony,
)
from apps.sanctuary.services.held_content_access import (
    is_under_active_safety_hold,
)


@dataclass(frozen=True)
class PostSharePreview:
    kind: str
    object_id: int
    slug: str
    title: str
    description: str
    canonical_path: str
    image_key: str | None
    image_alt: str


def resolve_post_share_preview(
    *,
    kind: str,
    slug: str,
    viewer,
) -> PostSharePreview | None:
    normalized_kind = _clean(kind).lower()
    normalized_slug = _clean(slug)

    if not normalized_kind or not normalized_slug:
        return None

    if normalized_kind == "moment":
        return _resolve_moment(
            slug=normalized_slug,
            viewer=viewer,
        )

    if normalized_kind == "journey":
        return _resolve_journey(
            slug=normalized_slug,
            viewer=viewer,
        )

    if normalized_kind == "prayer":
        return _resolve_prayer(
            slug=normalized_slug,
            viewer=viewer,
        )

    if normalized_kind == "testimony":
        return _resolve_testimony(
            slug=normalized_slug,
            viewer=viewer,
        )

    return None


# MARK: - Moment


def _resolve_moment(
    *,
    slug: str,
    viewer,
) -> PostSharePreview | None:
    moment = (
        Moment.objects
        .filter(
            slug=slug,
        )
        .first()
    )

    if not _is_publicly_shareable(
        moment,
        viewer=viewer,
    ):
        return None

    caption = _excerpt(
        moment.caption,
        limit=180,
    )

    title = (
        _excerpt(
            moment.caption,
            limit=72,
        )
        or "Moment on TownLIT"
    )

    return PostSharePreview(
        kind="moment",
        object_id=moment.pk,
        slug=moment.slug,
        title=title,
        description=(
            caption
            or "A Moment shared on TownLIT."
        ),
        canonical_path=_canonical_path(
            path=f"/moments/{moment.slug}",
            kind="moment",
            object_id=moment.pk,
        ),
        image_key=_moment_image_key(
            moment
        ),
        image_alt="TownLIT Moment",
    )


def _moment_image_key(
    moment: Moment,
) -> str | None:
    if (
        moment.media_kind == "video"
        and moment.thumbnail
        and moment.thumbnail.name
    ):
        return _clean_storage_key(
            moment.thumbnail.name
        )

    return _clean_storage_key(
        moment.cover_image_key()
    )


# MARK: - Journey


def _resolve_journey(
    *,
    slug: str,
    viewer,
) -> PostSharePreview | None:
    entry = (
        JourneyEntry.objects
        .select_related(
            "journey",
            "content_type",
        )
        .filter(
            slug=slug,
        )
        .first()
    )

    if not _is_publicly_shareable(
        entry,
        viewer=viewer,
    ):
        return None

    now = timezone.now()

    if entry.published_at > now:
        return None

    is_historical = bool(
        entry.archived_at is not None
        or entry.expires_at <= now
    )

    if (
        is_historical
        and entry.retention_policy
        != JourneyRetentionPolicy.KEEP
    ):
        return None

    return PostSharePreview(
        kind="journey",
        object_id=entry.pk,
        slug=entry.slug,
        title="Journey on TownLIT",
        description=(
            "View this Journey entry on TownLIT."
        ),
        canonical_path=_canonical_path(
            path=f"/posts/{entry.slug}",
            kind="journey",
            object_id=entry.pk,
        ),
        image_key=_clean_storage_key(
            getattr(
                entry.thumbnail,
                "name",
                None,
            )
        ),
        image_alt="TownLIT Journey",
    )


# MARK: - Prayer


def _resolve_prayer(
    *,
    slug: str,
    viewer,
) -> PostSharePreview | None:
    prayer = (
        Prayer.objects
        .filter(
            slug=slug,
        )
        .first()
    )

    if not _is_publicly_shareable(
        prayer,
        viewer=viewer,
    ):
        return None

    caption = _excerpt(
        prayer.caption,
        limit=180,
    )

    return PostSharePreview(
        kind="prayer",
        object_id=prayer.pk,
        slug=prayer.slug,
        title="Prayer on TownLIT",
        description=(
            caption
            or "A prayer shared on TownLIT."
        ),
        canonical_path=_canonical_path(
            path=f"/posts/{prayer.slug}",
            kind="prayer",
            object_id=prayer.pk,
        ),
        image_key=_clean_storage_key(
            getattr(
                prayer.image,
                "name",
                None,
            )
        ),
        image_alt="TownLIT Prayer",
    )


# MARK: - Testimony


def _resolve_testimony(
    *,
    slug: str,
    viewer,
) -> PostSharePreview | None:
    testimony = (
        Testimony.objects
        .filter(
            slug=slug,
        )
        .first()
    )

    if not _is_publicly_shareable(
        testimony,
        viewer=viewer,
    ):
        return None

    title = (
        _excerpt(
            testimony.title,
            limit=72,
        )
        or "Testimony on TownLIT"
    )

    description = (
        _excerpt(
            testimony.content,
            limit=180,
        )
        or "A testimony shared on TownLIT."
    )

    return PostSharePreview(
        kind="testimony",
        object_id=testimony.pk,
        slug=testimony.slug,
        title=title,
        description=description,
        canonical_path=_canonical_path(
            path=f"/posts/{testimony.slug}",
            kind="testimony",
            object_id=testimony.pk,
        ),
        image_key=_testimony_image_key(
            testimony
        ),
        image_alt=(
            f"{title} on TownLIT"
        ),
    )


def _testimony_image_key(
    testimony: Testimony,
) -> str | None:
    if (
        testimony.type
        == Testimony.TYPE_VIDEO
    ):
        return _clean_storage_key(
            getattr(
                testimony.thumbnail,
                "name",
                None,
            )
        )

    if (
        testimony.type
        == Testimony.TYPE_AUDIO
    ):
        return _clean_storage_key(
            getattr(
                testimony.audio_artwork,
                "name",
                None,
            )
        )

    return None


# MARK: - Public policy


def _is_publicly_shareable(
    obj,
    *,
    viewer,
) -> bool:
    if obj is None:
        return False

    if (
        getattr(
            obj,
            "visibility",
            None,
        )
        != VISIBILITY_GLOBAL
    ):
        return False

    if not getattr(
        obj,
        "is_active",
        True,
    ):
        return False

    if getattr(
        obj,
        "is_hidden",
        False,
    ):
        return False

    if getattr(
        obj,
        "is_suspended",
        False,
    ):
        return False

    if is_under_active_safety_hold(
        obj
    ):
        return False

    is_available = getattr(
        obj,
        "is_available",
        None,
    )

    if (
        callable(is_available)
        and not is_available()
    ):
        return False

    try:
        return bool(
            VisibilityPolicy.can_view(
                viewer=viewer,
                obj=obj,
            )
        )
    except Exception:
        return False


# MARK: - Helpers


def _canonical_path(
    *,
    path: str,
    kind: str,
    object_id: int,
) -> str:
    query = urlencode(
        {
            "kind": kind,
            "seed_id": object_id,
        }
    )

    return f"{path}?{query}"


def _excerpt(
    value,
    *,
    limit: int,
) -> str:
    normalized = " ".join(
        str(value or "").split()
    )

    if len(normalized) <= limit:
        return normalized

    return (
        normalized[
            : max(0, limit - 1)
        ].rstrip()
        + "…"
    )


def _clean(
    value,
) -> str:
    return str(
        value or ""
    ).strip()


def _clean_storage_key(
    value,
) -> str | None:
    key = _clean(
        value
    ).lstrip("/")

    return key or None