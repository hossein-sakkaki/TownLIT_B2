# apps/core/square/tests/test_square_stable_cursor.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from urllib.parse import urlencode

from django.test import SimpleTestCase

from apps.core.square.stable_cursor import (
    SquareStableCursorCodec,
    SquareStableCursorError,
    SquareStableCursorState,
    SquareStableFeedCursor,
    SquareStableSourceBoundary,
)


class SquareStableCursorCodecTests(
    SimpleTestCase
):
    def setUp(self):
        self.viewer = SimpleNamespace(
            id=17,
            is_authenticated=True,
        )

        self.boundary = datetime(
            2026,
            9,
            16,
            16,
            30,
            tzinfo=timezone.utc,
        )

    def _state(
        self,
    ) -> SquareStableCursorState:
        return SquareStableCursorState(
            viewer_key="user:17",
            kind="all",
            mode="",
            source_kinds=[
                "moment",
                "pray",
                "testimony",
            ],
            remaining_ids={
                "moment": [
                    32,
                    41,
                ],
                "pray": [
                    32,
                ],
                "testimony": [
                    110,
                ],
            },
            boundaries={
                "moment":
                    SquareStableSourceBoundary(
                        published_at=self.boundary,
                        object_id=41,
                    ),
                "pray":
                    SquareStableSourceBoundary(
                        published_at=self.boundary,
                        object_id=32,
                    ),
            },
            exhausted_kinds={
                "testimony",
            },
        )

    def test_cursor_round_trip_preserves_state(
        self,
    ):
        token = (
            SquareStableCursorCodec
            .encode(
                self._state()
            )
        )

        decoded = (
            SquareStableCursorCodec
            .decode(
                token,
                viewer=self.viewer,
                kind="all",
                mode=None,
            )
        )

        self.assertEqual(
            decoded.viewer_key,
            "user:17",
        )

        self.assertEqual(
            decoded.remaining_ids[
                "moment"
            ],
            [
                32,
                41,
            ],
        )

        self.assertEqual(
            decoded.remaining_ids[
                "pray"
            ],
            [
                32,
            ],
        )

        self.assertEqual(
            decoded.boundaries[
                "moment"
            ].object_id,
            41,
        )

        self.assertIn(
            "testimony",
            decoded.exhausted_kinds,
        )

    def test_same_numeric_id_is_separate_across_sources(
        self,
    ):
        token = (
            SquareStableCursorCodec
            .encode(
                self._state()
            )
        )

        decoded = (
            SquareStableCursorCodec
            .decode(
                token,
                viewer=self.viewer,
                kind="all",
                mode=None,
            )
        )

        self.assertIn(
            32,
            decoded.remaining_ids[
                "moment"
            ],
        )

        self.assertIn(
            32,
            decoded.remaining_ids[
                "pray"
            ],
        )

    def test_full_next_url_is_accepted(
        self,
    ):
        token = (
            SquareStableCursorCodec
            .encode(
                self._state()
            )
        )

        url = (
            "https://api.townlit.com/square/?"
            + urlencode(
                {
                    "cursor": token,
                }
            )
        )

        self.assertTrue(
            SquareStableCursorCodec
            .is_stable_cursor(
                url
            )
        )

        decoded = (
            SquareStableCursorCodec
            .decode(
                url,
                viewer=self.viewer,
                kind="all",
                mode=None,
            )
        )

        self.assertEqual(
            decoded.viewer_key,
            "user:17",
        )

    def test_cursor_rejects_different_viewer(
        self,
    ):
        token = (
            SquareStableCursorCodec
            .encode(
                self._state()
            )
        )

        other_viewer = SimpleNamespace(
            id=18,
            is_authenticated=True,
        )

        with self.assertRaises(
            SquareStableCursorError
        ):
            (
                SquareStableCursorCodec
                .decode(
                    token,
                    viewer=other_viewer,
                    kind="all",
                    mode=None,
                )
            )

    def test_cursor_rejects_different_mode(
        self,
    ):
        token = (
            SquareStableCursorCodec
            .encode(
                self._state()
            )
        )

        with self.assertRaises(
            SquareStableCursorError
        ):
            (
                SquareStableCursorCodec
                .decode(
                    token,
                    viewer=self.viewer,
                    kind="all",
                    mode="trending",
                )
            )


class SquareStableFeedCursorTests(
    SimpleTestCase
):
    def test_global_tie_breaker_includes_source_kind(
        self,
    ):
        published_at = datetime(
            2026,
            9,
            16,
            18,
            0,
            tzinfo=timezone.utc,
        )

        prayer = SimpleNamespace(
            id=32,
            square_kind="pray",
            published_at=published_at,
            hybrid_score=10.0,
        )

        moment = SimpleNamespace(
            id=32,
            square_kind="moment",
            published_at=published_at,
            hybrid_score=10.0,
        )

        ranked = (
            SquareStableFeedCursor
            ._rank_objects(
                [
                    prayer,
                    moment,
                ],
                mode=None,
                viewer=None,
            )
        )

        self.assertEqual(
            [
                item.square_kind
                for item in ranked
            ],
            [
                "moment",
                "pray",
            ],
        )

    def test_remaining_ids_keep_sources_separate(
        self,
    ):
        state = SquareStableCursorState(
            viewer_key="anonymous",
            kind="all",
            mode="",
            source_kinds=[
                "moment",
                "pray",
            ],
        )

        objects = [
            SimpleNamespace(
                id=32,
                square_kind="moment",
            ),
            SimpleNamespace(
                id=32,
                square_kind="pray",
            ),
        ]

        remaining = (
            SquareStableFeedCursor
            ._remaining_ids_from_objects(
                state=state,
                objects=objects,
            )
        )

        self.assertEqual(
            remaining,
            {
                "moment": [
                    32,
                ],
                "pray": [
                    32,
                ],
            },
        )

    def test_emitted_identity_is_not_carried_forward(
        self,
    ):
        state = SquareStableCursorState(
            viewer_key="anonymous",
            kind="all",
            mode="",
            source_kinds=[
                "moment",
            ],
        )

        unshown = [
            SimpleNamespace(
                id=2,
                square_kind="moment",
            ),
            SimpleNamespace(
                id=3,
                square_kind="moment",
            ),
        ]

        remaining = (
            SquareStableFeedCursor
            ._remaining_ids_from_objects(
                state=state,
                objects=unshown,
            )
        )

        self.assertNotIn(
            1,
            remaining["moment"],
        )

        self.assertEqual(
            remaining["moment"],
            [
                2,
                3,
            ],
        )