# apps/profiles/services/people_suggestion_context.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.profiles.models.relationships import Friendship
from apps.profiles.selectors.friends import get_friend_user_ids


CustomUser = get_user_model()


def build_people_suggestion_mutual_preview_map(
    *,
    viewer,
    candidates,
    request,
    preview_limit: int = 5,
) -> dict[int, list[dict]]:
    """
    Build serialized mutual-friend previews for people recommendations.
    """

    candidate_ids = [
        candidate.id
        for candidate in candidates
    ]

    preview_map = {
        candidate_id: []
        for candidate_id in candidate_ids
    }

    if not candidate_ids:
        return preview_map

    viewer_friend_ids = set(
        get_friend_user_ids(viewer)
    )

    if not viewer_friend_ids:
        return preview_map

    edges = (
        Friendship.objects
        .filter(
            status="accepted",
            is_active=True,
            from_user__is_active=True,
            from_user__is_deleted=False,
            from_user__is_suspended=False,
            to_user__is_active=True,
            to_user__is_deleted=False,
            to_user__is_suspended=False,
        )
        .filter(
            Q(
                from_user_id__in=viewer_friend_ids,
                to_user_id__in=candidate_ids,
            )
            | Q(
                to_user_id__in=viewer_friend_ids,
                from_user_id__in=candidate_ids,
            )
        )
        .values(
            "from_user_id",
            "to_user_id",
        )
    )

    mutual_ids_by_candidate = {
        candidate_id: set()
        for candidate_id in candidate_ids
    }

    candidate_id_set = set(candidate_ids)

    for edge in edges:
        from_user_id = edge["from_user_id"]
        to_user_id = edge["to_user_id"]

        if (
            from_user_id in candidate_id_set
            and to_user_id in viewer_friend_ids
        ):
            mutual_ids_by_candidate[
                from_user_id
            ].add(
                to_user_id
            )

        elif (
            to_user_id in candidate_id_set
            and from_user_id in viewer_friend_ids
        ):
            mutual_ids_by_candidate[
                to_user_id
            ].add(
                from_user_id
            )

    preview_ids_by_candidate = {
        candidate_id: sorted(mutual_ids)[
            :preview_limit
        ]
        for candidate_id, mutual_ids
        in mutual_ids_by_candidate.items()
    }

    all_mutual_ids = {
        mutual_id
        for mutual_ids in preview_ids_by_candidate.values()
        for mutual_id in mutual_ids
    }

    if not all_mutual_ids:
        return preview_map

    mutual_users = (
        CustomUser.objects
        .filter(
            id__in=all_mutual_ids,
            is_active=True,
            is_deleted=False,
            is_suspended=False,
        )
        .select_related(
            "label",
            "member_profile",
        )
    )

    mutual_users_by_id = {
        mutual_user.id: mutual_user
        for mutual_user in mutual_users
    }

    for candidate_id, mutual_ids in (
        preview_ids_by_candidate.items()
    ):
        mutual_objects = [
            mutual_users_by_id[mutual_id]
            for mutual_id in mutual_ids
            if mutual_id in mutual_users_by_id
        ]

        preview_map[candidate_id] = (
            UserMiniSerializer(
                mutual_objects,
                many=True,
                context={
                    "request": request,
                },
            ).data
        )

    return preview_map