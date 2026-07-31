# apps/creative_editor/tests/test_revision.py

from __future__ import annotations

import copy

from django.test import TestCase

from apps.creative_editor.services.compositions import (
    CreativeRevisionConflict,
    create_composition,
    update_composition,
)
from apps.creative_editor.tests.factories import (
    build_test_document,
    composition_data,
    create_test_user,
    ensure_test_font,
)


class CreativeRevisionTests(
    TestCase
):
    """
    Test optimistic revision locking.
    """

    def setUp(self):
        self.user = create_test_user(
            email=(
                "creative-revision@example.com"
            ),
        )

        ensure_test_font()

        self.document = (
            build_test_document()
        )

        self.composition = (
            create_composition(
                owner=self.user,
                validated_data=(
                    composition_data(
                        self.document
                    )
                ),
            )
        )

    def test_document_change_increments_revision(
        self,
    ):
        updated = copy.deepcopy(
            self.document
        )

        updated[
            "layers"
        ][0][
            "content"
        ][
            "text"
        ] = "Updated text"

        result = update_composition(
            composition=self.composition,
            expected_revision=1,
            validated_data={
                "document": updated,
            },
        )

        self.assertTrue(
            result.document_changed
        )

        self.assertEqual(
            result.composition.revision,
            2,
        )

    def test_same_document_keeps_revision(
        self,
    ):
        result = update_composition(
            composition=self.composition,
            expected_revision=1,
            validated_data={
                "document": copy.deepcopy(
                    self.document
                ),
            },
        )

        self.assertFalse(
            result.document_changed
        )

        self.assertEqual(
            result.composition.revision,
            1,
        )

    def test_old_revision_is_rejected(
        self,
    ):
        updated = copy.deepcopy(
            self.document
        )

        updated[
            "layers"
        ][0][
            "content"
        ][
            "text"
        ] = "First update"

        update_composition(
            composition=self.composition,
            expected_revision=1,
            validated_data={
                "document": updated,
            },
        )

        with self.assertRaises(
            CreativeRevisionConflict
        ):
            update_composition(
                composition=self.composition,
                expected_revision=1,
                validated_data={
                    "title": "Old edit",
                },
            )