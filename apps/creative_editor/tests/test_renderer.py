# apps/creative_editor/tests/test_renderer.py

from __future__ import annotations

from django.test import TestCase

from PIL import (
    Image,
    features,
)

from apps.creative_editor.services.compositions import (
    create_composition,
)
from apps.creative_editor.services.renderer import (
    CreativeCompositionRenderer,
    CreativeRenderContext,
)
from apps.creative_editor.tests.factories import (
    build_test_document,
    composition_data,
    create_test_user,
    ensure_test_font,
)


class CreativeRendererTests(
    TestCase
):
    """
    Test canonical composition rendering.
    """

    def setUp(self):
        self.user = create_test_user(
            email=(
                "creative-renderer@example.com"
            ),
        )

        ensure_test_font()

    def test_renders_gradient_and_text(
        self,
    ):
        document = build_test_document(
            text=(
                "God is faithful\n"
                "خدا وفادار است"
            ),
        )

        composition = create_composition(
            owner=self.user,
            validated_data=(
                composition_data(
                    document
                )
            ),
        )

        renderer = (
            CreativeCompositionRenderer()
        )

        image = renderer.render(
            context=CreativeRenderContext(
                composition=composition,
                document=document,
                revision=1,
            )
        )

        self.assertIsInstance(
            image,
            Image.Image,
        )

        self.assertEqual(
            image.size,
            (
                540,
                960,
            ),
        )

        self.assertEqual(
            image.mode,
            "RGBA",
        )

    def test_raqm_is_available(
        self,
    ):
        self.assertTrue(
            features.check("raqm")
        )