# apps/creative_editor/tests/factories.py

from __future__ import annotations

import uuid

from django.contrib.auth import (
    get_user_model,
)

from apps.creative_editor.models import (
    CreativeComposition,
    CreativeFont,
)


def create_test_user(
    *,
    email: str,
):
    """
    Create one test user.
    """

    User = get_user_model()

    return User.objects.create_user(
        email=email,
        password="test-password-123",
    )


def ensure_test_font() -> CreativeFont:
    """
    Ensure one renderer font exists.
    """

    font, _ = (
        CreativeFont.objects
        .update_or_create(
            key="townlit-sans-regular",
            defaults={
                "display_name": (
                    "TownLIT Sans"
                ),
                "postscript_name": (
                    "DejaVuSans"
                ),
                "category": (
                    CreativeFont.Category
                    .SANS_SERIF
                ),
                "source": (
                    CreativeFont.Source.SYSTEM
                ),
                "supports_ltr": True,
                "supports_rtl": True,
                "supports_bold": True,
                "supports_italic": False,
                "minimum_size": 12,
                "maximum_size": 160,
                "preview_text": (
                    "Creative Editor"
                ),
                "sort_order": 10,
                "is_active": True,
            },
        )
    )

    return font


def build_test_document(
    *,
    width: int = 540,
    height: int = 960,
    text: str = "God is faithful",
) -> dict:
    """
    Build one valid test document.
    """

    return {
        "version": 1,
        "canvas": {
            "width": width,
            "height": height,
            "background": {
                "type": "gradient",
                "colors": [
                    "#071A33FF",
                    "#D8A94AFF",
                ],
                "angle": 45,
            },
        },
        "layers": [
            {
                "id": str(
                    uuid.uuid4()
                ),
                "type": "text",
                "z_index": 10,
                "opacity": 1,
                "is_hidden": False,
                "is_locked": False,
                "transform": {
                    "center_x": 0.5,
                    "center_y": 0.5,
                    "width": 0.8,
                    "height": 0.3,
                    "scale": 1,
                    "rotation": 0,
                    "flip_x": False,
                    "flip_y": False,
                },
                "content": {
                    "text": text,
                    "font_key": (
                        "townlit-sans-regular"
                    ),
                    "font_size": 44,
                    "color": "#FFFFFFFF",
                    "alignment": "center",
                    "direction": "auto",
                    "line_spacing": 8,
                    "background_color": (
                        "#00000033"
                    ),
                    "stroke_color": (
                        "#000000AA"
                    ),
                    "stroke_width": 1,
                    "entity_version": 1,
                    "entities": [],
                },
            },
        ],
    }


def composition_data(
    document: dict,
) -> dict:
    """
    Build composition service data.
    """

    canvas = document["canvas"]

    return {
        "title": "Creative Editor Test",
        "visibility": (
            CreativeComposition.Visibility
            .PRIVATE
        ),
        "source_mode": (
            CreativeComposition.SourceMode
            .GENERATED_BACKGROUND
        ),
        "canvas_width": canvas["width"],
        "canvas_height": canvas["height"],
        "format_version": 1,
        "document": document,
        "metadata": {
            "test": True,
        },
    }