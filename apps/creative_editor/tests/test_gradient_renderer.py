# apps/creative_editor/tests/test_gradient_renderer.py

from __future__ import annotations

from django.test import (
    SimpleTestCase,
)

from PIL import Image

from apps.creative_editor.services.gradient_renderer import (
    build_linear_gradient,
)


class GradientRendererTests(
    SimpleTestCase
):
    """
    Test the optimized gradient renderer.
    """

    def test_builds_expected_canvas_size(
        self,
    ):
        image = build_linear_gradient(
            width=540,
            height=960,
            colors=[
                "#071A33FF",
                "#D8A94AFF",
            ],
            angle=45,
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

    def test_supports_multiple_colors(
        self,
    ):
        image = build_linear_gradient(
            width=320,
            height=320,
            colors=[
                "#071A33FF",
                "#D8A94AFF",
                "#FFFFFFFF",
            ],
            angle=90,
        )

        self.assertEqual(
            image.size,
            (
                320,
                320,
            ),
        )