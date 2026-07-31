# apps/core/journey_streams/network.py

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import (
    get_user_model,
)
from django.db.models import Q

from apps.core.boundaries.services.policy import (
    BoundaryPolicy,
)
from apps.core.journey_streams.constants import (
    JOURNEY_RELATION_DIRECT,
    JOURNEY_RELATION_SECOND_DEGREE,
    JOURNEY_STREAM_MAX_DIRECT_FRIENDS,
    JOURNEY_STREAM_MAX_SECOND_DEGREE_USERS,
)
from apps.profiles.models.relationships import (
    Friendship,
)


CustomUser = get_user_model()


@dataclass(frozen=True)
class JourneyAudienceMember:
    """
    One eligible user in the Journey graph.
    """

    user_id: int

    relationship: str

    mutual_connector_count: int


@dataclass(frozen=True)
class JourneyNetworkAudience:
    """
    Final Journey audience.
    """

    members: tuple[
        JourneyAudienceMember,
        ...
    ]

    @property
    def user_ids(
        self,
    ) -> set[int]:
        return {
            member.user_id
            for member in self.members
        }

    @property
    def by_user_id(
        self,
    ) -> dict[
        int,
        JourneyAudienceMember,
    ]:
        return {
            member.user_id: member
            for member in self.members
        }


def _accepted_friend_edges_for_user(
    *,
    user_id: int,
):
    """
    Return direct accepted friendship edges.
    """

    return (
        Friendship.objects
        .filter(
            Q(
                from_user_id=user_id
            )
            | Q(
                to_user_id=user_id
            ),
            status="accepted",
            is_active=True,
        )
        .values_list(
            "from_user_id",
            "to_user_id",
        )[
            :JOURNEY_STREAM_MAX_DIRECT_FRIENDS
        ]
    )


def _direct_friend_ids(
    *,
    viewer_id: int,
) -> set[int]:
    """
    Resolve direct accepted friends.
    """

    output: set[int] = set()

    for (
        from_user_id,
        to_user_id,
    ) in _accepted_friend_edges_for_user(
        user_id=viewer_id,
    ):
        counterpart_id = (
            to_user_id
            if from_user_id
            == viewer_id
            else from_user_id
        )

        if counterpart_id != viewer_id:
            output.add(
                counterpart_id
            )

    return output


def _second_degree_map(
    *,
    viewer_id: int,
    direct_friend_ids: set[int],
) -> dict[int, set[int]]:
    """
    Map second-degree user to mutual connectors.

    Example:
    second_degree_map[target] = {
        direct_friend_a,
        direct_friend_b,
    }
    """

    if not direct_friend_ids:
        return {}

    edges = (
        Friendship.objects
        .filter(
            Q(
                from_user_id__in=(
                    direct_friend_ids
                )
            )
            | Q(
                to_user_id__in=(
                    direct_friend_ids
                )
            ),
            status="accepted",
            is_active=True,
        )
        .values_list(
            "from_user_id",
            "to_user_id",
        )[
            :JOURNEY_STREAM_MAX_SECOND_DEGREE_USERS
        ]
    )

    output: dict[
        int,
        set[int],
    ] = {}

    for (
        from_user_id,
        to_user_id,
    ) in edges:
        if (
            from_user_id
            in direct_friend_ids
        ):
            connector_id = (
                from_user_id
            )

            candidate_id = (
                to_user_id
            )

        elif (
            to_user_id
            in direct_friend_ids
        ):
            connector_id = (
                to_user_id
            )

            candidate_id = (
                from_user_id
            )

        else:
            continue

        if candidate_id == viewer_id:
            continue

        if (
            candidate_id
            in direct_friend_ids
        ):
            continue

        output.setdefault(
            candidate_id,
            set(),
        ).add(
            connector_id
        )

    return output


def _available_user_ids(
    *,
    user_ids: set[int],
) -> set[int]:
    """
    Remove unavailable accounts.
    """

    if not user_ids:
        return set()

    return set(
        CustomUser.objects
        .filter(
            id__in=user_ids,
            is_active=True,
            is_deleted=False,
            is_suspended=False,
            is_account_paused=False,
        )
        .values_list(
            "id",
            flat=True,
        )
    )


def _peace_visible_user_ids(
    *,
    viewer,
    user_ids: set[int],
) -> set[int]:
    """
    Apply Boundary and Stillness.

    Boundary:
    - bidirectional exclusion

    Stillness:
    - viewer -> target exclusion
    """

    if not user_ids:
        return set()

    users = (
        CustomUser.objects
        .filter(
            id__in=user_ids
        )
        .only(
            "id",
        )
    )

    visible_ids: set[int] = set()

    for target_user in users:
        try:
            if (
                BoundaryPolicy
                .has_boundary_between(
                    viewer,
                    target_user,
                )
            ):
                continue

            if (
                BoundaryPolicy
                .is_in_stillness(
                    owner=viewer,
                    target=target_user,
                )
            ):
                continue

            visible_ids.add(
                target_user.pk
            )

        except Exception:
            # Journey Stream fails closed.
            continue

    return visible_ids


def build_journey_network_audience(
    *,
    viewer,
) -> JourneyNetworkAudience:
    """
    Build the Journey graph for one viewer.
    """

    if (
        not viewer
        or not getattr(
            viewer,
            "is_authenticated",
            False,
        )
    ):
        return JourneyNetworkAudience(
            members=(),
        )

    direct_ids = _direct_friend_ids(
        viewer_id=viewer.pk,
    )

    second_degree_map = (
        _second_degree_map(
            viewer_id=viewer.pk,
            direct_friend_ids=direct_ids,
        )
    )

    all_candidate_ids = (
        direct_ids
        | set(
            second_degree_map.keys()
        )
    )

    available_ids = (
        _available_user_ids(
            user_ids=all_candidate_ids,
        )
    )

    peace_visible_ids = (
        _peace_visible_user_ids(
            viewer=viewer,
            user_ids=available_ids,
        )
    )

    final_direct_ids = (
        direct_ids
        & peace_visible_ids
    )

    final_second_degree_ids = (
        set(
            second_degree_map.keys()
        )
        & peace_visible_ids
    )

    members: list[
        JourneyAudienceMember
    ] = []

    for user_id in sorted(
        final_direct_ids
    ):
        members.append(
            JourneyAudienceMember(
                user_id=user_id,
                relationship=(
                    JOURNEY_RELATION_DIRECT
                ),
                mutual_connector_count=0,
            )
        )

    for user_id in sorted(
        final_second_degree_ids
    ):
        members.append(
            JourneyAudienceMember(
                user_id=user_id,
                relationship=(
                    JOURNEY_RELATION_SECOND_DEGREE
                ),
                mutual_connector_count=len(
                    second_degree_map.get(
                        user_id,
                        set(),
                    )
                ),
            )
        )

    return JourneyNetworkAudience(
        members=tuple(
            members
        ),
    )