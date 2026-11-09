# apps/core/streams/tests/test_stream_policy.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.core.streams.constants import (
    STREAM_SCOPE_GLOBAL,
    STREAM_SCOPE_MESSENGER,
    STREAM_SCOPE_PROFILE,
    STREAM_SCOPE_SQUARE,
    STREAM_SQUARE_MAX_EXTENSIONS,
    STREAM_SQUARE_MAX_ITEMS,
    STREAM_SQUARE_PAGE_SIZE,
)
from apps.core.streams.engine import StreamEngine
from apps.core.streams.views import StreamViewSet


class StreamPolicyContractTests(SimpleTestCase):
    @staticmethod
    def _context(
        *,
        scope=STREAM_SCOPE_SQUARE,
        extension=0,
        cursor=None,
    ):
        return SimpleNamespace(
            scope=scope,
            extension=extension,
            cursor=cursor,
        )

    def test_square_policy_is_three_batches_of_seven_items(self):
        self.assertEqual(
            STREAM_SQUARE_PAGE_SIZE,
            7,
        )
        self.assertEqual(
            STREAM_SQUARE_MAX_EXTENSIONS,
            3,
        )
        self.assertEqual(
            STREAM_SQUARE_MAX_ITEMS,
            21,
        )

    def test_square_first_batch_reserves_one_slot_for_seed(self):
        context = self._context(
            scope=STREAM_SCOPE_SQUARE,
            extension=0,
            cursor=None,
        )

        self.assertTrue(
            StreamEngine._is_first_page(
                context=context,
            )
        )
        self.assertEqual(
            StreamEngine._effective_limit(
                context=context,
                is_first_page=True,
            ),
            6,
        )

    def test_square_extension_batches_request_seven_related_items(self):
        for extension in (1, 2):
            with self.subTest(extension=extension):
                context = self._context(
                    scope=STREAM_SCOPE_SQUARE,
                    extension=extension,
                )

                self.assertEqual(
                    StreamEngine._effective_limit(
                        context=context,
                        is_first_page=False,
                    ),
                    7,
                )

    def test_square_extension_offsets_preserve_three_distinct_batches(self):
        expected_offsets = {
            0: 0,
            1: 6,
            2: 13,
        }

        for extension, expected_offset in expected_offsets.items():
            with self.subTest(extension=extension):
                context = self._context(
                    scope=STREAM_SCOPE_SQUARE,
                    extension=extension,
                )

                self.assertEqual(
                    StreamEngine._effective_offset(
                        context=context,
                    ),
                    expected_offset,
                )

    def test_messenger_uses_same_limited_extension_policy(self):
        context = self._context(
            scope=STREAM_SCOPE_MESSENGER,
            extension=2,
        )

        self.assertEqual(
            StreamEngine._page_size(
                context=context,
            ),
            7,
        )
        self.assertEqual(
            StreamEngine._effective_offset(
                context=context,
            ),
            13,
        )

    def test_profile_cursor_page_is_not_treated_as_first_page(self):
        context = self._context(
            scope=STREAM_SCOPE_PROFILE,
            extension=0,
            cursor=object(),
        )

        self.assertFalse(
            StreamEngine._is_first_page(
                context=context,
            )
        )

    def test_square_extension_three_is_blocked(self):
        view = StreamViewSet()

        for extension in (0, 1, 2):
            with self.subTest(extension=extension):
                context = self._context(
                    scope=STREAM_SCOPE_SQUARE,
                    extension=extension,
                )

                self.assertFalse(
                    view._is_square_limit_reached(
                        context,
                    )
                )

        blocked_context = self._context(
            scope=STREAM_SCOPE_SQUARE,
            extension=3,
        )

        self.assertTrue(
            view._is_square_limit_reached(
                blocked_context,
            )
        )

    def test_non_limited_scope_is_not_blocked_by_square_extension_limit(self):
        view = StreamViewSet()

        context = self._context(
            scope=STREAM_SCOPE_GLOBAL,
            extension=100,
        )

        self.assertFalse(
            view._is_square_limit_reached(
                context,
            )
        )

    def test_continue_requires_policy_room_and_full_batch(self):
        view = StreamViewSet()

        extension_zero = self._context(
            extension=0,
        )
        extension_one = self._context(
            extension=1,
        )
        extension_two = self._context(
            extension=2,
        )

        self.assertTrue(
            view._can_continue_for_results(
                context=extension_zero,
                results_count=7,
            )
        )
        self.assertTrue(
            view._can_continue_for_results(
                context=extension_one,
                results_count=7,
            )
        )
        self.assertFalse(
            view._can_continue_for_results(
                context=extension_two,
                results_count=7,
            )
        )
        self.assertFalse(
            view._can_continue_for_results(
                context=extension_zero,
                results_count=6,
            )
        )

    def test_limited_scope_never_exposes_cursor_pagination(self):
        view = StreamViewSet()

        context = self._context(
            scope=STREAM_SCOPE_SQUARE,
        )

        self.assertIsNone(
            view._resolved_next_cursor(
                context=context,
                next_cursor="cursor-value",
            )
        )

    def test_non_limited_scope_preserves_cursor_pagination(self):
        view = StreamViewSet()

        context = self._context(
            scope=STREAM_SCOPE_GLOBAL,
        )

        self.assertEqual(
            view._resolved_next_cursor(
                context=context,
                next_cursor="cursor-value",
            ),
            "cursor-value",
        )

    def test_policy_payload_exposes_server_owned_square_limits(self):
        view = StreamViewSet()

        payload = view._policy_payload(
            self._context(
                scope=STREAM_SCOPE_SQUARE,
            )
        )

        self.assertEqual(
            payload,
            {
                "scope": STREAM_SCOPE_SQUARE,
                "is_limited": True,
                "batch_size": 7,
                "batch_count": 3,
                "max_items": 21,
            },
        )