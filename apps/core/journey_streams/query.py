# apps/core/journey_streams/query.py

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.contenttypes.models import (
    ContentType,
)
from django.db.models import (
    Case,
    IntegerField,
    Value,
    When,
)
from django.utils import timezone

from apps.core.boundaries.query import (
    BoundaryVisibilityQuery,
)
from apps.core.journey_streams.constants import (
    JOURNEY_RELATION_DIRECT,
    JOURNEY_STREAM_MAX_CANDIDATE_JOURNEYS,
    JOURNEY_STREAM_MAX_CANDIDATE_MEMBERS,
)
from apps.core.journey_streams.context import (
    JourneyStreamContext,
    encode_journey_stream_cursor,
)
from apps.core.journey_streams.network import (
    JourneyNetworkAudience,
)
from apps.core.journey_streams.ranking import (
    JourneyRankInput,
    calculate_journey_rank,
)
from apps.core.visibility.query import (
    VisibilityQuery,
)
from apps.posts.models.journey import (
    Journey,
    JourneyEntry,
    JourneyEntryView,
)
from apps.profiles.models.member import (
    Member,
)


# Owner Journey must always remain above network recommendations.
JOURNEY_STREAM_OWNER_RANK_SCORE = 2_000_000_000


@dataclass(frozen=True)
class RankedJourney:
    """
    One ranked Journey result.
    """

    journey: Journey

    rank_score: int

    latest_published_at: object

    latest_entry_id: int


@dataclass(frozen=True)
class JourneyStreamPage:
    """
    One Journey Stream page.
    """

    items: tuple[
        RankedJourney,
        ...
    ]

    next_cursor: str | None

    has_more: bool

    seen_entry_ids: frozenset[int]


@dataclass(frozen=True)
class ResolvedJourneyAudienceMember:
    """
    Resolved stream relationship for one Member.
    """

    relationship: str

    mutual_connector_count: int

    is_owner: bool = False


def _owner_member(
    *,
    context: JourneyStreamContext,
) -> Member | None:
    """
    Resolve the authenticated viewer's active Member profile.

    Journey publishing is Member-only, so Guest users naturally
    return no owner Member here.
    """

    viewer = context.viewer

    viewer_id = getattr(
        viewer,
        "pk",
        None,
    )

    if not viewer_id:
        return None

    return (
        Member.objects
        .select_related(
            "user",
            "user__label",
        )
        .filter(
            user_id=viewer_id,
            is_active=True,
        )
        .first()
    )


def _eligible_members(
    *,
    context: JourneyStreamContext,
    audience: JourneyNetworkAudience,
) -> tuple[
    dict[int, Member],
    dict[int, ResolvedJourneyAudienceMember],
    int | None,
]:
    """
    Resolve eligible Member profiles.

    Owner:
    - always eligible when the viewer has an active Member profile
    - privacy does not hide a profile from its own owner

    Direct friends:
    - public or private profiles

    Friends of friends:
    - public profiles only
    """

    audience_by_user_id = (
        audience.by_user_id
    )

    member_by_id: dict[
        int,
        Member,
    ] = {}

    relationship_by_member_id: dict[
        int,
        ResolvedJourneyAudienceMember,
    ] = {}

    owner = _owner_member(
        context=context,
    )

    owner_member_id: int | None = None

    if owner is not None:
        owner_member_id = owner.pk

        member_by_id[
            owner.pk
        ] = owner

        # Keep the public API contract backward-compatible.
        # iOS already understands the direct relationship.
        relationship_by_member_id[
            owner.pk
        ] = ResolvedJourneyAudienceMember(
            relationship=(
                JOURNEY_RELATION_DIRECT
            ),
            mutual_connector_count=0,
            is_owner=True,
        )

    if not audience_by_user_id:
        return (
            member_by_id,
            relationship_by_member_id,
            owner_member_id,
        )

    network_members = (
        Member.objects
        .select_related(
            "user",
            "user__label",
        )
        .filter(
            user_id__in=(
                audience.user_ids
            ),
            is_active=True,
        )
        .exclude(
            pk=owner_member_id
        )
        .order_by(
            "pk"
        )[
            :JOURNEY_STREAM_MAX_CANDIDATE_MEMBERS
        ]
    )

    for member in network_members:
        audience_member = (
            audience_by_user_id.get(
                member.user_id
            )
        )

        if audience_member is None:
            continue

        is_direct = (
            audience_member.relationship
            == JOURNEY_RELATION_DIRECT
        )

        is_private = bool(
            getattr(
                member,
                "is_privacy",
                False,
            )
        )

        if (
            is_private
            and not is_direct
        ):
            continue

        member_by_id[
            member.pk
        ] = member

        relationship_by_member_id[
            member.pk
        ] = ResolvedJourneyAudienceMember(
            relationship=(
                audience_member.relationship
            ),
            mutual_connector_count=int(
                audience_member
                .mutual_connector_count
                or 0
            ),
            is_owner=False,
        )

    return (
        member_by_id,
        relationship_by_member_id,
        owner_member_id,
    )


def _visible_live_entries(
    *,
    context: JourneyStreamContext,
    member_ids: set[int],
    owner_member_id: int | None,
):
    """
    Resolve live Journey Entries visible to the viewer.

    Owner Entries are ordered first so they cannot be lost
    when the candidate queryset is sliced.

    Audio Catalog display relations are loaded eagerly for
    the Stream music payload. This only optimizes read-time
    serialization and does not modify rights, usage grants,
    publishing, or administration behavior.
    """

    if not member_ids:
        return JourneyEntry.objects.none()

    member_ct = (
        ContentType.objects
        .get_for_model(
            Member,
            for_concrete_model=False,
        )
    )

    now = timezone.now()

    queryset = (
        JourneyEntry.objects
        .select_related(
            "journey",
            "music_track",
            "music_variant",

            # Canonical Audio Catalog metadata used by
            # TrackListSerializer in the Stream response.
            "music_track__catalog",
            "music_track__rights",
        )
        .prefetch_related(
            # Contributors are reverse/multi-value relations,
            # so they must be prefetched rather than joined.
            "music_track__contributor_links__contributor",
        )
        .filter(
            content_type=member_ct,
            object_id__in=member_ids,
            is_active=True,
            is_hidden=False,
            is_suspended=False,
            published_at__lte=now,
            expires_at__gt=now,
            archived_at__isnull=True,
        )
    )

    queryset = VisibilityQuery.for_viewer(
        viewer=context.viewer,
        base_queryset=queryset,
    )

    queryset = (
        BoundaryVisibilityQuery
        .exclude_boundary_conflicts(
            queryset,
            viewer=context.viewer,
        )
    )

    if owner_member_id is not None:
        queryset = queryset.annotate(
            _journey_owner_priority=Case(
                When(
                    object_id=owner_member_id,
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        return queryset.order_by(
            "-_journey_owner_priority",
            "-published_at",
            "-id",
        )

    return queryset.order_by(
        "-published_at",
        "-id",
    )


def _is_after_cursor(
    *,
    rank_score: int,
    latest_published_at,
    latest_entry_id: int,
    context: JourneyStreamContext,
) -> bool:
    """
    Return True when item belongs after cursor.
    """

    cursor = context.cursor

    if cursor is None:
        return True

    item_key = (
        rank_score,
        latest_published_at,
        latest_entry_id,
    )

    cursor_key = (
        cursor.rank_score,
        cursor.latest_published_at,
        cursor.latest_entry_id,
    )

    return item_key < cursor_key


def build_journey_stream_page(
    *,
    context: JourneyStreamContext,
    audience: JourneyNetworkAudience,
) -> JourneyStreamPage:
    """
    Build one ranked Journey Stream page.

    The authenticated Member's own Journey is included before
    network recommendations.
    """

    (
        member_by_id,
        relationship_by_member_id,
        owner_member_id,
    ) = _eligible_members(
        context=context,
        audience=audience,
    )

    member_ids = set(
        member_by_id.keys()
    )

    if not member_ids:
        return JourneyStreamPage(
            items=(),
            next_cursor=None,
            has_more=False,
            seen_entry_ids=frozenset(),
        )

    candidate_entry_limit = (
        JOURNEY_STREAM_MAX_CANDIDATE_JOURNEYS
        * 12
    )

    visible_entries = list(
        _visible_live_entries(
            context=context,
            member_ids=member_ids,
            owner_member_id=owner_member_id,
        )[
            :candidate_entry_limit
        ]
    )

    if not visible_entries:
        return JourneyStreamPage(
            items=(),
            next_cursor=None,
            has_more=False,
            seen_entry_ids=frozenset(),
        )

    all_entry_ids = [
        entry.pk
        for entry in visible_entries
    ]

    persisted_seen_entry_ids = set(
        JourneyEntryView.objects
        .filter(
            viewer_id=context.viewer.pk,
            entry_id__in=all_entry_ids,
        )
        .values_list(
            "entry_id",
            flat=True,
        )
    )

    owner_entry_ids = {
        entry.pk
        for entry in visible_entries
        if (
            owner_member_id is not None
            and entry.object_id
            == owner_member_id
        )
    }

    # The owner must never see their own Journey as unseen.
    seen_entry_ids = frozenset(
        persisted_seen_entry_ids
        | owner_entry_ids
    )

    entries_by_journey_id: dict[
        int,
        list[JourneyEntry],
    ] = {}

    for entry in visible_entries:
        entries_by_journey_id.setdefault(
            entry.journey_id,
            [],
        ).append(
            entry
        )

    journey_ids = list(
        entries_by_journey_id.keys()
    )[
        :JOURNEY_STREAM_MAX_CANDIDATE_JOURNEYS
    ]

    journey_map = {
        journey.pk: journey
        for journey in (
            Journey.objects
            .filter(
                pk__in=journey_ids
            )
            .only(
                "id",
                "slug",
                "content_type_id",
                "object_id",
                "local_date",
                "timezone_name",
                "palette_mode",
                "display_seed",
                "created_at",
                "updated_at",
            )
        )
    }

    ranked_items: list[
        RankedJourney
    ] = []

    for journey_id in journey_ids:
        journey = journey_map.get(
            journey_id
        )

        if journey is None:
            continue

        entries = (
            entries_by_journey_id.get(
                journey_id,
                [],
            )
        )

        if not entries:
            continue

        owner_member = member_by_id.get(
            journey.object_id
        )

        relationship = (
            relationship_by_member_id.get(
                journey.object_id
            )
        )

        if (
            owner_member is None
            or relationship is None
        ):
            continue

        entries.sort(
            key=lambda entry: (
                entry.sequence,
                entry.pk,
            )
        )

        unseen_entries_count = sum(
            1
            for entry in entries
            if entry.pk
            not in seen_entry_ids
        )

        latest_entry = max(
            entries,
            key=lambda entry: (
                entry.published_at,
                entry.pk,
            ),
        )

        if relationship.is_owner:
            rank_score = (
                JOURNEY_STREAM_OWNER_RANK_SCORE
            )
        else:
            rank_score = (
                calculate_journey_rank(
                    JourneyRankInput(
                        relationship=(
                            relationship
                            .relationship
                        ),
                        mutual_connector_count=(
                            relationship
                            .mutual_connector_count
                        ),
                        unseen_entries_count=(
                            unseen_entries_count
                        ),
                        active_entries_count=len(
                            entries
                        ),
                    )
                )
            )

        if not _is_after_cursor(
            rank_score=rank_score,
            latest_published_at=(
                latest_entry.published_at
            ),
            latest_entry_id=(
                latest_entry.pk
            ),
            context=context,
        ):
            continue

        journey.ordered_entries = entries

        journey._journey_stream_owner = (
            owner_member
        )

        journey._journey_stream_relationship = (
            relationship.relationship
        )

        journey._journey_stream_mutual_count = (
            relationship
            .mutual_connector_count
        )

        journey._journey_stream_rank_score = (
            rank_score
        )

        journey._journey_stream_is_owner = (
            relationship.is_owner
        )

        ranked_items.append(
            RankedJourney(
                journey=journey,
                rank_score=rank_score,
                latest_published_at=(
                    latest_entry
                    .published_at
                ),
                latest_entry_id=(
                    latest_entry.pk
                ),
            )
        )

    ranked_items.sort(
        key=lambda item: (
            item.rank_score,
            item.latest_published_at,
            item.latest_entry_id,
        ),
        reverse=True,
    )

    has_more = (
        len(ranked_items)
        > context.page_size
    )

    page_items = ranked_items[
        :context.page_size
    ]

    next_cursor = None

    if (
        has_more
        and page_items
    ):
        last_item = page_items[-1]

        next_cursor = (
            encode_journey_stream_cursor(
                rank_score=(
                    last_item.rank_score
                ),
                latest_published_at=(
                    last_item
                    .latest_published_at
                ),
                latest_entry_id=(
                    last_item.latest_entry_id
                ),
            )
        )

    return JourneyStreamPage(
        items=tuple(
            page_items
        ),
        next_cursor=next_cursor,
        has_more=has_more,
        seen_entry_ids=seen_entry_ids,
    )