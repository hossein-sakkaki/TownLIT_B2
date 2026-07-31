# apps/posts/services/journeys/profile_ring.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.utils import timezone

from apps.core.boundaries.query import BoundaryVisibilityQuery
from apps.core.visibility.query import VisibilityQuery
from apps.posts.models.journey import JourneyEntry, JourneyEntryView


@dataclass(frozen=True)
class JourneyProfileRingResult:
    """
    Lightweight Journey state for profile avatars.
    """

    has_active_journey: bool

    active_journey_id: int | None = None
    active_journey_slug: str | None = None

    active_entries_count: int = 0
    unseen_entries_count: int = 0

    latest_entry_id: int | None = None
    latest_thumbnail_target: dict | None = None

    palette_mode: str | None = None
    expires_at: datetime | None = None

    def as_dict(self) -> dict:
        return {
            "has_active_journey": self.has_active_journey,
            "active_journey_id": self.active_journey_id,
            "active_journey_slug": self.active_journey_slug,
            "active_entries_count": self.active_entries_count,
            "unseen_entries_count": self.unseen_entries_count,
            "latest_entry_id": self.latest_entry_id,
            "latest_thumbnail_target": self.latest_thumbnail_target,
            "palette_mode": self.palette_mode,
            "expires_at": self.expires_at,
        }


def empty_journey_profile_ring() -> JourneyProfileRingResult:
    """
    Return a stable empty Ring payload.
    """

    return JourneyProfileRingResult(
        has_active_journey=False,
    )


def _active_owner_entries(
    *,
    owner_profile,
) -> QuerySet:
    """
    Return currently live entries for one owner.
    """

    owner_ct = ContentType.objects.get_for_model(
        owner_profile.__class__,
        for_concrete_model=False,
    )

    now = timezone.now()

    return (
        JourneyEntry.objects
        .select_related("journey")
        .filter(
            content_type=owner_ct,
            object_id=owner_profile.pk,
            is_active=True,
            is_hidden=False,
            is_suspended=False,
            published_at__lte=now,
            expires_at__gt=now,
            archived_at__isnull=True,
        )
        .order_by(
            "-published_at",
            "-sequence",
            "-id",
        )
    )


def build_journey_profile_ring(
    *,
    owner_profile,
    viewer=None,
    owner_can_see_all: bool = False,
) -> JourneyProfileRingResult:
    """
    Build one optimized Journey Ring payload.

    Owner:
    - sees the Ring while the Journey is live
    - own views never hide the Ring

    Visitor:
    - sees the Ring only while at least one
      visible active Entry remains unseen

    Anonymous:
    - sees globally visible active Entries
    """

    if (
        owner_profile is None
        or not getattr(
            owner_profile,
            "pk",
            None,
        )
    ):
        return empty_journey_profile_ring()

    entries = _active_owner_entries(
        owner_profile=owner_profile,
    )

    viewer_is_authenticated = bool(
        viewer
        and getattr(
            viewer,
            "is_authenticated",
            False,
        )
    )

    owner_user_id = getattr(
        owner_profile,
        "user_id",
        None,
    )

    is_owner = bool(
        viewer_is_authenticated
        and owner_user_id
        and viewer.pk == owner_user_id
    )

    owner_has_full_access = bool(
        owner_can_see_all
        or is_owner
    )

    if not owner_has_full_access:
        entries = VisibilityQuery.for_viewer(
            viewer=viewer,
            base_queryset=entries,
        )

        if viewer_is_authenticated:
            entries = (
                BoundaryVisibilityQuery
                .exclude_boundary_conflicts(
                    entries,
                    viewer=viewer,
                )
            )

    entry_rows = list(
        entries.values(
            "id",
            "journey_id",
            "journey__slug",
            "journey__palette_mode",
            "sequence",
            "published_at",
            "expires_at",
            "thumbnail",
        )
    )

    if not entry_rows:
        return empty_journey_profile_ring()

    # One Journey exists per local day.
    # The newest live Entry determines the active Journey.
    latest = entry_rows[0]
    active_journey_id = latest["journey_id"]

    active_journey_rows = [
        row
        for row in entry_rows
        if row["journey_id"]
        == active_journey_id
    ]

    if not active_journey_rows:
        return empty_journey_profile_ring()

    active_entry_ids = [
        row["id"]
        for row in active_journey_rows
    ]

    unseen_entry_ids = list(
        active_entry_ids
    )

    if (
        viewer_is_authenticated
        and not is_owner
        and active_entry_ids
    ):
        completed_entry_ids = set(
            JourneyEntryView.objects.filter(
                entry_id__in=active_entry_ids,
                viewer_id=viewer.pk,
                completed=True,
            ).values_list(
                "entry_id",
                flat=True,
            )
        )

        unseen_entry_ids = [
            entry_id
            for entry_id in active_entry_ids
            if entry_id
            not in completed_entry_ids
        ]

    unseen_entries_count = (
        0
        if is_owner
        else len(
            unseen_entry_ids
        )
    )

    # Visitors should not retain a Ring
    # after completing every active Entry.
    if (
        not is_owner
        and viewer_is_authenticated
        and unseen_entries_count == 0
    ):
        return empty_journey_profile_ring()

    expires_at = max(
        row["expires_at"]
        for row in active_journey_rows
    )

    now = timezone.now()

    if expires_at <= now:
        return empty_journey_profile_ring()

    latest_entry = max(
        active_journey_rows,
        key=lambda row: (
            row["published_at"],
            row["sequence"],
            row["id"],
        ),
    )

    latest_entry_id = latest_entry[
        "id"
    ]

    latest_thumbnail_target = None

    if latest_entry.get(
        "thumbnail"
    ):
        latest_thumbnail_target = {
            "app_label": "posts",
            "model": "journeyentry",
            "object_id": latest_entry_id,
            "field_name": "thumbnail",
            "kind": "thumbnail",
        }

    return JourneyProfileRingResult(
        has_active_journey=True,
        active_journey_id=
            active_journey_id,
        active_journey_slug=
            latest["journey__slug"],
        active_entries_count=
            len(active_journey_rows),
        unseen_entries_count=
            unseen_entries_count,
        latest_entry_id=
            latest_entry_id,
        latest_thumbnail_target=
            latest_thumbnail_target,
        palette_mode=
            latest[
                "journey__palette_mode"
            ],
        expires_at=
            expires_at,
    )