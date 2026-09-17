# apps/core/streams/tests/test_stream_suggested_users.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.streams.constants import (
    STREAM_SCOPE_SQUARE,
)
from apps.core.streams.suggested_users import (
    STREAM_MODULE_SUGGESTED_USERS,
    StreamSuggestedUsersComposer,
)
from apps.core.streams.views import StreamViewSet


class _FakeSuggestionQueryset:
    def __init__(
        self,
        users,
    ):
        self.users = users
        self.excluded_ids = None
        self.requested_slice = None

    def exclude(
        self,
        **kwargs,
    ):
        self.excluded_ids = kwargs.get(
            "id__in"
        )
        return self

    def __getitem__(
        self,
        item,
    ):
        self.requested_slice = item
        return self.users[item]


class StreamSuggestedUsersComposerTests(
    SimpleTestCase
):
    @staticmethod
    def _context(
        *,
        extension: int,
        authenticated: bool = True,
    ):
        return SimpleNamespace(
            scope=STREAM_SCOPE_SQUARE,
            extension=extension,
            seed_id=500,
            kind="moment",
            viewer=SimpleNamespace(
                id=42,
                is_authenticated=authenticated,
            ),
        )

    @staticmethod
    def _users(
        count: int = 14,
    ):
        return [
            SimpleNamespace(
                id=user_id
            )
            for user_id in range(
                1,
                count + 1,
            )
        ]

    @staticmethod
    def _serializer(
        candidates,
        *,
        many,
        context,
    ):
        return SimpleNamespace(
            data=[
                {
                    "id": candidate.id,
                }
                for candidate in candidates
            ]
        )

    @patch(
        "apps.core.streams.suggested_users."
        "build_people_suggestion_mutual_preview_map",
        return_value={},
    )
    @patch(
        "apps.core.streams.suggested_users."
        "PeopleSuggestionSerializer",
    )
    @patch(
        "apps.core.streams.suggested_users."
        "BoundaryPolicy.excluded_user_ids_for_suggestions",
        return_value={90, 91},
    )
    @patch(
        "apps.core.streams.suggested_users."
        "get_people_suggestions_queryset",
    )
    def test_first_batch_uses_first_seven_ranked_users(
        self,
        people_queryset,
        excluded_ids,
        serializer,
        _preview_map,
    ):
        queryset = _FakeSuggestionQueryset(
            self._users()
        )

        people_queryset.return_value = queryset
        serializer.side_effect = self._serializer

        module = (
            StreamSuggestedUsersComposer
            .build_module(
                context=self._context(
                    extension=0
                ),
                request=object(),
                results_count=7,
            )
        )

        self.assertIsNotNone(
            module
        )

        self.assertEqual(
            queryset.requested_slice,
            slice(0, 7, None),
        )

        self.assertEqual(
            queryset.excluded_ids,
            {90, 91},
        )

        self.assertEqual(
            module["type"],
            STREAM_MODULE_SUGGESTED_USERS,
        )

        self.assertEqual(
            [
                user["id"]
                for user in module["users"]
            ],
            [
                1,
                2,
                3,
                4,
                5,
                6,
                7,
            ],
        )

        self.assertGreaterEqual(
            module["after_item_position"],
            2,
        )

        self.assertLessEqual(
            module["after_item_position"],
            6,
        )

        excluded_ids.assert_called_once()

    @patch(
        "apps.core.streams.suggested_users."
        "build_people_suggestion_mutual_preview_map",
        return_value={},
    )
    @patch(
        "apps.core.streams.suggested_users."
        "PeopleSuggestionSerializer",
    )
    @patch(
        "apps.core.streams.suggested_users."
        "BoundaryPolicy.excluded_user_ids_for_suggestions",
        return_value=set(),
    )
    @patch(
        "apps.core.streams.suggested_users."
        "get_people_suggestions_queryset",
    )
    def test_third_batch_uses_next_seven_ranked_users(
        self,
        people_queryset,
        _excluded_ids,
        serializer,
        _preview_map,
    ):
        queryset = _FakeSuggestionQueryset(
            self._users()
        )

        people_queryset.return_value = queryset
        serializer.side_effect = self._serializer

        module = (
            StreamSuggestedUsersComposer
            .build_module(
                context=self._context(
                    extension=2
                ),
                request=object(),
                results_count=7,
            )
        )

        self.assertIsNotNone(
            module
        )

        self.assertEqual(
            queryset.requested_slice,
            slice(7, 14, None),
        )

        self.assertEqual(
            [
                user["id"]
                for user in module["users"]
            ],
            [
                8,
                9,
                10,
                11,
                12,
                13,
                14,
            ],
        )

    @patch(
        "apps.core.streams.suggested_users."
        "get_people_suggestions_queryset",
    )
    def test_second_batch_has_no_module(
        self,
        people_queryset,
    ):
        module = (
            StreamSuggestedUsersComposer
            .build_module(
                context=self._context(
                    extension=1
                ),
                request=object(),
                results_count=7,
            )
        )

        self.assertIsNone(
            module
        )

        people_queryset.assert_not_called()

    @patch(
        "apps.core.streams.suggested_users."
        "get_people_suggestions_queryset",
    )
    def test_partial_stream_batch_has_no_module(
        self,
        people_queryset,
    ):
        module = (
            StreamSuggestedUsersComposer
            .build_module(
                context=self._context(
                    extension=0
                ),
                request=object(),
                results_count=6,
            )
        )

        self.assertIsNone(
            module
        )

        people_queryset.assert_not_called()

    @patch(
        "apps.core.streams.suggested_users."
        "build_people_suggestion_mutual_preview_map",
        return_value={},
    )
    @patch(
        "apps.core.streams.suggested_users."
        "PeopleSuggestionSerializer",
    )
    @patch(
        "apps.core.streams.suggested_users."
        "BoundaryPolicy.excluded_user_ids_for_suggestions",
        return_value=set(),
    )
    @patch(
        "apps.core.streams.suggested_users."
        "get_people_suggestions_queryset",
    )
    def test_incomplete_user_set_suppresses_module(
        self,
        people_queryset,
        _excluded_ids,
        serializer,
        _preview_map,
    ):
        people_queryset.return_value = (
            _FakeSuggestionQueryset(
                self._users(
                    count=5
                )
            )
        )

        module = (
            StreamSuggestedUsersComposer
            .build_module(
                context=self._context(
                    extension=0
                ),
                request=object(),
                results_count=7,
            )
        )

        self.assertIsNone(
            module
        )

        serializer.assert_not_called()


class StreamCompositionPayloadTests(
    SimpleTestCase
):
    @patch(
        "apps.core.streams.views."
        "StreamSuggestedUsersComposer.build_module",
        return_value={
            "id":
                "suggested_users:moment:500:0",
            "type":
                "suggested_users",
            "after_item_position": 4,
            "users": [],
        },
    )
    def test_view_wraps_module_in_composition_payload(
        self,
        build_module,
    ):
        context = SimpleNamespace(
            scope=STREAM_SCOPE_SQUARE,
            extension=0,
            seed_id=500,
            kind="moment",
            viewer=SimpleNamespace(
                id=42,
                is_authenticated=True,
            ),
        )

        request = object()

        payload = (
            StreamViewSet()
            ._composition_payload(
                context=context,
                request=request,
                results_count=7,
            )
        )

        self.assertEqual(
            len(payload["modules"]),
            1,
        )

        self.assertEqual(
            payload["modules"][0]["type"],
            "suggested_users",
        )

        build_module.assert_called_once_with(
            context=context,
            request=request,
            results_count=7,
        )