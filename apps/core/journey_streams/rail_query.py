# apps/core/journey_streams/rail_query.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-03.
# Last Update by Hossein Sakkaki on 2026-09-03.

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
from apps.core.journey_streams.network import (
    JourneyNetworkAudience,
)
from apps.core.journey_streams.rail_context import (
    JourneyRailContext,
    encode_journey_rail_cursor,
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


@dataclass(frozen=True)
class ResolvedJourneyRailMember:
    """
    One resolved Rail owner.
    """

    member: Member
    relationship: str
    mutual_connector_count: int


@dataclass(frozen=True)
class JourneyRailItem:
    """
    One Rail avatar target.
    """

    journey: Journey
    owner: Member
    relationship: str
    mutual_connector_count: int

    active_entries_count: int
    unseen_entries_count: int

    latest_entry_id: int
    latest_published_at: object

    expires_at: object
    next_expiry_at: object


@dataclass(frozen=True)
class JourneyRailPage:
    """
    One Rail page.
    """

    items: tuple[
        JourneyRailItem,
        ...
    ]

    next_cursor: str | None
    has_more: bool


def _relationship_tier(
    relationship: str,
) -> int:
    """
    Direct friends always come first.
    """

    return (
        0
        if relationship
        == JOURNEY_RELATION_DIRECT
        else 1
    )


def _eligible_members(
    *,
    audience: JourneyNetworkAudience,
) -> dict[
    int,
    ResolvedJourneyRailMember,
]:
    """
    Resolve Rail Member profiles.

    Direct:
    - public or private profile

    Second degree:
    - public profile only
    """

    ordered_audience = sorted(
        audience.members,
        key=lambda item: (
            _relationship_tier(
                item.relationship
            ),
            -int(
                item.mutual_connector_count
                or 0
            ),
            item.user_id,
        ),
    )[
        :JOURNEY_STREAM_MAX_CANDIDATE_MEMBERS
    ]

    if not ordered_audience:
        return {}

    user_ids = {
        item.user_id
        for item in ordered_audience
    }

    members_by_user_id = {
        member.user_id: member
        for member in (
            Member.objects
            .select_related(
                "user",
                "user__label",
            )
            .filter(
                user_id__in=user_ids,
                is_active=True,
            )
        )
    }

    output: dict[
        int,
        ResolvedJourneyRailMember,
    ] = {}

    for audience_member in ordered_audience:
        member = members_by_user_id.get(
            audience_member.user_id
        )

        if member is None:
            continue

        is_direct = (
            audience_member.relationship
            == JOURNEY_RELATION_DIRECT
        )

        if (
            not is_direct
            and bool(
                getattr(
                    member,
                    "is_privacy",
                    False,
                )
            )
        ):
            continue

        output[member.pk] = (
            ResolvedJourneyRailMember(
                member=member,
                relationship=(
                    audience_member.relationship
                ),
                mutual_connector_count=max(
                    int(
                        audience_member
                        .mutual_connector_count
                        or 0
                    ),
                    0,
                ),
            )
        )

    return output


def _visible_live_entries(
    *,
    context: JourneyRailContext,
    members: dict[
        int,
        ResolvedJourneyRailMember,
    ],
):
    """
    Resolve live visible Rail entries.
    """

    if not members:
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
        )
        .filter(
            content_type=member_ct,
            object_id__in=members.keys(),
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

    direct_member_ids = [
        member_id
        for member_id, item
        in members.items()
        if (
            item.relationship
            == JOURNEY_RELATION_DIRECT
        )
    ]

    if direct_member_ids:
        queryset = queryset.annotate(
            _rail_direct_priority=Case(
                When(
                    object_id__in=(
                        direct_member_ids
                    ),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        queryset = queryset.order_by(
            "-_rail_direct_priority",
            "-published_at",
            "-id",
        )

    else:
        queryset = queryset.order_by(
            "-published_at",
            "-id",
        )

    candidate_limit = (
        JOURNEY_STREAM_MAX_CANDIDATE_JOURNEYS
        * 12
    )

    return queryset[
        :candidate_limit
    ]


def _selected_entries_by_owner(
    entries,
) -> dict[
    int,
    list[JourneyEntry],
]:
    """
    Keep one active Journey per owner.
    """

    grouped: dict[
        int,
        dict[
            int,
            list[JourneyEntry],
        ],
    ] = {}

    for entry in entries:
        grouped.setdefault(
            entry.object_id,
            {},
        ).setdefault(
            entry.journey_id,
            [],
        ).append(entry)

    selected: dict[
        int,
        list[JourneyEntry],
    ] = {}

    for member_id, journey_map in grouped.items():
        if not journey_map:
            continue

        best_entries = max(
            journey_map.values(),
            key=lambda values: max(
                (
                    entry.published_at,
                    entry.pk,
                )
                for entry in values
            ),
        )

        selected[member_id] = (
            best_entries
        )

    return selected


def _item_sort_key(
    item: JourneyRailItem,
):
    tier = _relationship_tier(
        item.relationship
    )

    mutual_order = (
        -item.mutual_connector_count
        if tier == 1
        else 0
    )

    return (
        tier,
        mutual_order,
        -item.latest_published_at.timestamp(),
        -item.latest_entry_id,
        item.owner.user_id,
    )


def _cursor_sort_key(
    context: JourneyRailContext,
):
    cursor = context.cursor

    if cursor is None:
        return None

    mutual_order = (
        -cursor.mutual_connector_count
        if cursor.relationship_tier == 1
        else 0
    )

    return (
        cursor.relationship_tier,
        mutual_order,
        -cursor.latest_published_at.timestamp(),
        -cursor.latest_entry_id,
        cursor.owner_user_id,
    )


def build_journey_rail_page(
    *,
    context: JourneyRailContext,
    audience: JourneyNetworkAudience,
) -> JourneyRailPage:
    """
    Build one strict relationship-tier Rail page.
    """

    members = _eligible_members(
        audience=audience,
    )

    if not members:
        return JourneyRailPage(
            items=(),
            next_cursor=None,
            has_more=False,
        )

    visible_entries = list(
        _visible_live_entries(
            context=context,
            members=members,
        )
    )

    if not visible_entries:
        return JourneyRailPage(
            items=(),
            next_cursor=None,
            has_more=False,
        )

    selected_by_owner = (
        _selected_entries_by_owner(
            visible_entries
        )
    )

    selected_entry_ids = [
        entry.pk
        for entries
        in selected_by_owner.values()
        for entry in entries
    ]

    seen_entry_ids = set(
        JourneyEntryView.objects
        .filter(
            viewer_id=context.viewer.pk,
            entry_id__in=(
                selected_entry_ids
            ),
        )
        .values_list(
            "entry_id",
            flat=True,
        )
    )

    items: list[
        JourneyRailItem
    ] = []

    for member_id, entries in (
        selected_by_owner.items()
    ):
        resolved = members.get(
            member_id
        )

        if (
            resolved is None
            or not entries
        ):
            continue

        entries.sort(
            key=lambda entry: (
                entry.sequence,
                entry.pk,
            )
        )

        latest_entry = max(
            entries,
            key=lambda entry: (
                entry.published_at,
                entry.pk,
            ),
        )

        unseen_count = sum(
            1
            for entry in entries
            if (
                entry.pk
                not in seen_entry_ids
            )
        )

        items.append(
            JourneyRailItem(
                journey=latest_entry.journey,
                owner=resolved.member,
                relationship=(
                    resolved.relationship
                ),
                mutual_connector_count=(
                    resolved
                    .mutual_connector_count
                ),
                active_entries_count=len(
                    entries
                ),
                unseen_entries_count=(
                    unseen_count
                ),
                latest_entry_id=(
                    latest_entry.pk
                ),
                latest_published_at=(
                    latest_entry.published_at
                ),
                expires_at=max(
                    entry.expires_at
                    for entry in entries
                ),
                next_expiry_at=min(
                    entry.expires_at
                    for entry in entries
                ),
            )
        )

    items.sort(
        key=_item_sort_key
    )

    cursor_key = _cursor_sort_key(
        context
    )

    if cursor_key is not None:
        items = [
            item
            for item in items
            if (
                _item_sort_key(item)
                > cursor_key
            )
        ]

    has_more = (
        len(items)
        > context.page_size
    )

    page_items = items[
        :context.page_size
    ]

    next_cursor = None

    if (
        has_more
        and page_items
    ):
        last_item = page_items[-1]

        next_cursor = (
            encode_journey_rail_cursor(
                relationship_tier=(
                    _relationship_tier(
                        last_item.relationship
                    )
                ),
                mutual_connector_count=(
                    last_item
                    .mutual_connector_count
                ),
                latest_published_at=(
                    last_item
                    .latest_published_at
                ),
                latest_entry_id=(
                    last_item.latest_entry_id
                ),
                owner_user_id=(
                    last_item.owner.user_id
                ),
            )
        )

    return JourneyRailPage(
        items=tuple(page_items),
        next_cursor=next_cursor,
        has_more=has_more,
    )