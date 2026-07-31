# apps/creative_editor/tests/test_render_jobs.py

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)
from apps.creative_editor.services.compositions import (
    create_composition,
    request_render,
)
from apps.creative_editor.tests.factories import (
    build_test_document,
    composition_data,
    create_test_user,
    ensure_test_font,
)


class CreativeRenderJobTests(
    TestCase
):
    """
    Test render job orchestration.
    """

    def setUp(self):
        self.user = create_test_user(
            email=(
                "creative-job@example.com"
            ),
        )

        ensure_test_font()

        document = build_test_document()

        self.composition = (
            create_composition(
                owner=self.user,
                validated_data=(
                    composition_data(
                        document
                    )
                ),
            )
        )

    @patch(
        "apps.creative_editor.services."
        "compositions._enqueue_render_job"
    )
    def test_same_revision_is_idempotent(
        self,
        enqueue_mock,
    ):
        first = request_render(
            composition=self.composition
        )

        second = request_render(
            composition=self.composition
        )

        self.assertTrue(
            first.created
        )

        self.assertFalse(
            second.created
        )

        self.assertEqual(
            first.job.pk,
            second.job.pk,
        )

        self.assertEqual(
            CreativeRenderJob.objects.count(),
            1,
        )

    @patch(
        "apps.creative_editor.services."
        "compositions._enqueue_render_job"
    )
    def test_render_request_sets_rendering_status(
        self,
        enqueue_mock,
    ):
        request_render(
            composition=self.composition
        )

        self.composition.refresh_from_db()

        self.assertEqual(
            self.composition.status,
            CreativeComposition.Status.RENDERING,
        )