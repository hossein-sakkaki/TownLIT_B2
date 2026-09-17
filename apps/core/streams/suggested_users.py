# apps/core/streams/suggested_users.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.core.streams.composition import (
    SUGGESTED_USERS_LIMIT,
    StreamCompositionPolicy,
)
from apps.core.streams.constants import (
    STREAM_SQUARE_PAGE_SIZE,
)
from apps.profiles.selectors.people_suggestions import (
    get_people_suggestions_queryset,
)
from apps.profiles.serializers.friendships import (
    PeopleSuggestionSerializer,
)
from apps.profiles.services.people_suggestion_context import (
    build_people_suggestion_mutual_preview_map,
)


STREAM_MODULE_SUGGESTED_USERS = "suggested_users"
SUGGESTED_USERS_CYCLE_LIMIT = (
    SUGGESTED_USERS_LIMIT * 2
)

class StreamSuggestedUsersComposer:
    """
    Build the server-owned suggested-users Stream module.

    Stream content remains separate from composition modules.
    """

    @classmethod
    def build_module(
        cls,
        *,
        context,
        request,
        results_count: int,
    ) -> dict | None:
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=context
            )
        )

        if placement is None:
            return None

        if int(results_count or 0) < STREAM_SQUARE_PAGE_SIZE:
            return None

        viewer = context.viewer

        if viewer is None:
            return None

        queryset = (
            get_people_suggestions_queryset(
                viewer
            )
        )

        excluded_ids = (
            BoundaryPolicy
            .excluded_user_ids_for_suggestions(
                viewer
            )
        )

        if excluded_ids:
            queryset = queryset.exclude(
                id__in=excluded_ids
            )

        offset = cls._candidate_offset(
            extension=context.extension
        )

        limit = placement.user_limit

        candidates = list(
            queryset[
                offset:offset + limit
            ]
        )

        if len(candidates) != limit:
            return None

        mutual_preview_map = (
            build_people_suggestion_mutual_preview_map(
                viewer=viewer,
                candidates=candidates,
                request=request,
                preview_limit=5,
            )
        )

        serializer = PeopleSuggestionSerializer(
            candidates,
            many=True,
            context={
                "request": request,
                "mutual_preview_map":
                    mutual_preview_map,
            },
        )

        return {
            "id": cls._module_id(
                context=context
            ),
            "type": STREAM_MODULE_SUGGESTED_USERS,
            "after_item_position":
                placement.after_item_position,
            "users": serializer.data,
        }

    @staticmethod
    def _candidate_offset(
        *,
        extension: int,
    ) -> int:
        if int(extension or 0) == 2:
            return SUGGESTED_USERS_LIMIT

        return 0

    @staticmethod
    def _module_id(
        *,
        context,
    ) -> str:
        return (
            "suggested_users:"
            f"{context.kind}:"
            f"{context.seed_id}:"
            f"{context.extension}"
        )