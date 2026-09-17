# apps/core/streams/tests/test_stream_composition.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.core.streams.composition import (
    SUGGESTED_USERS_LIMIT,
    SUGGESTED_USERS_MAX_AFTER_ITEM_POSITION,
    SUGGESTED_USERS_MIN_AFTER_ITEM_POSITION,
    StreamCompositionPolicy,
)
from apps.core.streams.constants import (
    STREAM_SCOPE_MESSENGER,
    STREAM_SCOPE_SQUARE,
)


class StreamCompositionPolicyTests(SimpleTestCase):
    @staticmethod
    def _context(
        *,
        extension: int,
        scope: str = STREAM_SCOPE_SQUARE,
        viewer_id: int = 42,
        authenticated: bool = True,
        seed_id: int = 100,
        kind: str = "moment",
    ):
        viewer = SimpleNamespace(
            id=viewer_id,
            is_authenticated=authenticated,
        )

        return SimpleNamespace(
            extension=extension,
            scope=scope,
            viewer=viewer,
            seed_id=seed_id,
            kind=kind,
        )

    def test_first_square_batch_can_include_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=0,
                )
            )
        )

        self.assertIsNotNone(
            placement
        )

        self.assertEqual(
            placement.user_limit,
            SUGGESTED_USERS_LIMIT,
        )

    def test_second_square_batch_does_not_include_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=1,
                )
            )
        )

        self.assertIsNone(
            placement
        )

    def test_third_square_batch_can_include_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=2,
                )
            )
        )

        self.assertIsNotNone(
            placement
        )

        self.assertEqual(
            placement.user_limit,
            7,
        )

    def test_placement_is_after_content_item_two_through_six(self):
        for seed_id in range(
            1,
            100,
        ):
            with self.subTest(
                seed_id=seed_id
            ):
                placement = (
                    StreamCompositionPolicy
                    .suggested_users_placement(
                        context=self._context(
                            extension=0,
                            seed_id=seed_id,
                        )
                    )
                )

                self.assertIsNotNone(
                    placement
                )

                self.assertGreaterEqual(
                    placement.after_item_position,
                    SUGGESTED_USERS_MIN_AFTER_ITEM_POSITION,
                )

                self.assertLessEqual(
                    placement.after_item_position,
                    SUGGESTED_USERS_MAX_AFTER_ITEM_POSITION,
                )

    def test_placement_is_stable_for_same_stream_context(self):
        context = self._context(
            extension=0,
            viewer_id=17,
            seed_id=908,
            kind="testimony",
        )

        first = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=context
            )
        )

        second = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=context
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_placement_is_not_fixed_to_one_position(self):
        positions = set()

        for seed_id in range(
            1,
            100,
        ):
            placement = (
                StreamCompositionPolicy
                .suggested_users_placement(
                    context=self._context(
                        extension=0,
                        seed_id=seed_id,
                    )
                )
            )

            self.assertIsNotNone(
                placement
            )

            positions.add(
                placement.after_item_position
            )

        self.assertGreater(
            len(positions),
            1,
        )

    def test_messenger_stream_does_not_receive_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=0,
                    scope=STREAM_SCOPE_MESSENGER,
                )
            )
        )

        self.assertIsNone(
            placement
        )

    def test_guest_square_stream_does_not_receive_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=0,
                    authenticated=False,
                )
            )
        )

        self.assertIsNone(
            placement
        )

    def test_invalid_viewer_id_does_not_receive_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=0,
                    viewer_id=0,
                )
            )
        )

        self.assertIsNone(
            placement
        )

    def test_invalid_seed_does_not_receive_suggested_users(self):
        placement = (
            StreamCompositionPolicy
            .suggested_users_placement(
                context=self._context(
                    extension=0,
                    seed_id=0,
                )
            )
        )

        self.assertIsNone(
            placement
        )