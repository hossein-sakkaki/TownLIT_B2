# apps/creative_editor/validators/document.py

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping

from django.core.exceptions import ValidationError


DOCUMENT_VERSION = 1

MAX_DOCUMENT_BYTES = 96 * 1024
MAX_LAYERS = 30
MAX_TEXT_LAYERS = 12
MAX_STICKER_LAYERS = 20

MAX_TEXT_CHARACTERS = 500
MAX_ENTITIES_PER_TEXT = 50

MIN_NORMALIZED_VALUE = -0.5
MAX_NORMALIZED_VALUE = 1.5

MIN_SCALE = 0.05
MAX_SCALE = 10.0

MIN_ROTATION = -6.28319
MAX_ROTATION = 6.28319

MIN_OPACITY = 0.0
MAX_OPACITY = 1.0

MIN_FONT_SIZE = 8.0
MAX_FONT_SIZE = 240.0

HEX_COLOR_PATTERN = re.compile(
    r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"
)

ALLOWED_LAYER_TYPES = {
    "text",
    "sticker",
}

ALLOWED_TEXT_ALIGNMENTS = {
    "leading",
    "center",
    "trailing",
    "justified",
}

ALLOWED_TEXT_DIRECTIONS = {
    "auto",
    "ltr",
    "rtl",
}

ALLOWED_ENTITY_TYPES = {
    "hashtag",
    "mention",
}

ALLOWED_CANVAS_BACKGROUND_TYPES = {
    "transparent",
    "color",
    "gradient",
    "image",
}


def validate_creative_document(value) -> None:
    """
    Validate a versioned creative editor document.
    """

    if not isinstance(value, Mapping):
        raise ValidationError(
            "Creative document must be an object."
        )

    _validate_document_size(value)

    version = value.get("version")

    if version != DOCUMENT_VERSION:
        raise ValidationError(
            {
                "version": (
                    f"Unsupported creative document version: "
                    f"{version!r}."
                )
            }
        )

    canvas = value.get("canvas")

    if not isinstance(canvas, Mapping):
        raise ValidationError(
            {
                "canvas": "Canvas must be an object.",
            }
        )

    _validate_canvas(canvas)

    layers = value.get("layers")

    if not isinstance(layers, list):
        raise ValidationError(
            {
                "layers": "Layers must be a list.",
            }
        )

    if len(layers) > MAX_LAYERS:
        raise ValidationError(
            {
                "layers": (
                    f"Creative document supports up to "
                    f"{MAX_LAYERS} layers."
                ),
            }
        )

    text_count = 0
    sticker_count = 0
    seen_layer_ids: set[str] = set()

    for index, layer in enumerate(layers):
        if not isinstance(layer, Mapping):
            raise ValidationError(
                {
                    "layers": (
                        f"Layer at index {index} must be an object."
                    ),
                }
            )

        layer_id = _validate_layer_identity(
            layer,
            index=index,
        )

        if layer_id in seen_layer_ids:
            raise ValidationError(
                {
                    "layers": (
                        f"Duplicate layer id at index {index}."
                    ),
                }
            )

        seen_layer_ids.add(layer_id)

        layer_type = layer.get("type")

        if layer_type not in ALLOWED_LAYER_TYPES:
            raise ValidationError(
                {
                    "layers": (
                        f"Unsupported layer type at index "
                        f"{index}: {layer_type!r}."
                    ),
                }
            )

        _validate_transform(
            layer.get("transform"),
            index=index,
        )

        _validate_common_layer_fields(
            layer,
            index=index,
        )

        content = layer.get("content")

        if layer_type == "text":
            text_count += 1

            _validate_text_content(
                content,
                index=index,
            )

        elif layer_type == "sticker":
            sticker_count += 1

            _validate_sticker_content(
                content,
                index=index,
            )

    if text_count > MAX_TEXT_LAYERS:
        raise ValidationError(
            {
                "layers": (
                    f"Creative document supports up to "
                    f"{MAX_TEXT_LAYERS} text layers."
                ),
            }
        )

    if sticker_count > MAX_STICKER_LAYERS:
        raise ValidationError(
            {
                "layers": (
                    f"Creative document supports up to "
                    f"{MAX_STICKER_LAYERS} sticker layers."
                ),
            }
        )


def _validate_document_size(
    value,
) -> None:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "Creative document is not valid JSON."
        ) from exc

    if len(payload) > MAX_DOCUMENT_BYTES:
        raise ValidationError(
            (
                "Creative document is too large. "
                f"Maximum size is {MAX_DOCUMENT_BYTES} bytes."
            )
        )


def _validate_canvas(
    canvas: Mapping,
) -> None:
    width = _positive_integer(
        canvas.get("width"),
        field="canvas.width",
    )

    height = _positive_integer(
        canvas.get("height"),
        field="canvas.height",
    )

    if width > 8192 or height > 8192:
        raise ValidationError(
            {
                "canvas": (
                    "Canvas dimensions cannot exceed "
                    "8192 × 8192."
                ),
            }
        )

    background = canvas.get(
        "background",
        {
            "type": "transparent",
        },
    )

    if not isinstance(background, Mapping):
        raise ValidationError(
            {
                "canvas.background": (
                    "Background must be an object."
                ),
            }
        )

    background_type = background.get(
        "type",
        "transparent",
    )

    if (
        background_type
        not in ALLOWED_CANVAS_BACKGROUND_TYPES
    ):
        raise ValidationError(
            {
                "canvas.background.type": (
                    "Unsupported background type."
                ),
            }
        )

    if background_type == "color":
        _validate_optional_color(
            background.get("color"),
            field="canvas.background.color",
            required=True,
        )

    if background_type == "gradient":
        colors = background.get("colors")

        if (
            not isinstance(colors, list)
            or not 2 <= len(colors) <= 4
        ):
            raise ValidationError(
                {
                    "canvas.background.colors": (
                        "Gradient requires 2 to 4 colors."
                    ),
                }
            )

        for color in colors:
            _validate_optional_color(
                color,
                field="canvas.background.colors",
                required=True,
            )

        angle = background.get(
            "angle",
            0,
        )

        _number_in_range(
            angle,
            minimum=-360,
            maximum=360,
            field="canvas.background.angle",
        )

    if background_type == "image":
        source = background.get("source")

        if source not in {
            "composition_source",
            "content_reference",
        }:
            raise ValidationError(
                {
                    "canvas.background.source": (
                        "Invalid image background source."
                    ),
                }
            )


def _validate_layer_identity(
    layer: Mapping,
    *,
    index: int,
) -> str:
    value = str(
        layer.get("id") or ""
    ).strip()

    try:
        uuid.UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(
            {
                "layers": (
                    f"Layer at index {index} requires "
                    "a valid UUID id."
                ),
            }
        )

    return value.lower()


def _validate_common_layer_fields(
    layer: Mapping,
    *,
    index: int,
) -> None:
    z_index = layer.get(
        "z_index",
        index,
    )

    if (
        isinstance(z_index, bool)
        or not isinstance(z_index, int)
        or z_index < 0
        or z_index > 10_000
    ):
        raise ValidationError(
            {
                "layers": (
                    f"Invalid z_index at layer {index}."
                ),
            }
        )

    opacity = layer.get(
        "opacity",
        1,
    )

    _number_in_range(
        opacity,
        minimum=MIN_OPACITY,
        maximum=MAX_OPACITY,
        field=f"layers[{index}].opacity",
    )

    for name in (
        "is_hidden",
        "is_locked",
    ):
        value = layer.get(
            name,
            False,
        )

        if not isinstance(value, bool):
            raise ValidationError(
                {
                    "layers": (
                        f"{name} must be boolean at "
                        f"layer {index}."
                    ),
                }
            )


def _validate_transform(
    transform,
    *,
    index: int,
) -> None:
    if not isinstance(transform, Mapping):
        raise ValidationError(
            {
                "layers": (
                    f"Layer {index} requires a transform."
                ),
            }
        )

    for field in (
        "center_x",
        "center_y",
        "width",
        "height",
    ):
        _number_in_range(
            transform.get(field),
            minimum=MIN_NORMALIZED_VALUE,
            maximum=MAX_NORMALIZED_VALUE,
            field=f"layers[{index}].transform.{field}",
        )

    if transform.get("width", 0) <= 0:
        raise ValidationError(
            {
                "layers": (
                    f"Layer {index} width must be positive."
                ),
            }
        )

    if transform.get("height", 0) <= 0:
        raise ValidationError(
            {
                "layers": (
                    f"Layer {index} height must be positive."
                ),
            }
        )

    _number_in_range(
        transform.get(
            "scale",
            1,
        ),
        minimum=MIN_SCALE,
        maximum=MAX_SCALE,
        field=f"layers[{index}].transform.scale",
    )

    _number_in_range(
        transform.get(
            "rotation",
            0,
        ),
        minimum=MIN_ROTATION,
        maximum=MAX_ROTATION,
        field=f"layers[{index}].transform.rotation",
    )

    flip_x = transform.get(
        "flip_x",
        False,
    )

    flip_y = transform.get(
        "flip_y",
        False,
    )

    if not isinstance(flip_x, bool):
        raise ValidationError(
            {
                "layers": (
                    f"Layer {index} flip_x must be boolean."
                ),
            }
        )

    if not isinstance(flip_y, bool):
        raise ValidationError(
            {
                "layers": (
                    f"Layer {index} flip_y must be boolean."
                ),
            }
        )


def _validate_text_content(
    content,
    *,
    index: int,
) -> None:
    if not isinstance(content, Mapping):
        raise ValidationError(
            {
                "layers": (
                    f"Text layer {index} content must "
                    "be an object."
                ),
            }
        )

    text = content.get("text")

    if not isinstance(text, str):
        raise ValidationError(
            {
                "layers": (
                    f"Text layer {index} requires text."
                ),
            }
        )

    if len(text) > MAX_TEXT_CHARACTERS:
        raise ValidationError(
            {
                "layers": (
                    f"Text layer {index} supports up to "
                    f"{MAX_TEXT_CHARACTERS} characters."
                ),
            }
        )

    font_key = str(
        content.get("font_key") or ""
    ).strip()

    if not font_key:
        raise ValidationError(
            {
                "layers": (
                    f"Text layer {index} requires font_key."
                ),
            }
        )

    _number_in_range(
        content.get("font_size"),
        minimum=MIN_FONT_SIZE,
        maximum=MAX_FONT_SIZE,
        field=f"layers[{index}].content.font_size",
    )

    alignment = content.get(
        "alignment",
        "center",
    )

    if alignment not in ALLOWED_TEXT_ALIGNMENTS:
        raise ValidationError(
            {
                "layers": (
                    f"Invalid text alignment at layer {index}."
                ),
            }
        )

    direction = content.get(
        "direction",
        "auto",
    )

    if direction not in ALLOWED_TEXT_DIRECTIONS:
        raise ValidationError(
            {
                "layers": (
                    f"Invalid text direction at layer {index}."
                ),
            }
        )

    _validate_optional_color(
        content.get(
            "color",
            "#FFFFFFFF",
        ),
        field=f"layers[{index}].content.color",
        required=True,
    )

    _number_in_range(
        content.get(
            "line_spacing",
            0,
        ),
        minimum=-20,
        maximum=100,
        field=f"layers[{index}].content.line_spacing",
    )

    _validate_optional_color(
        content.get("background_color"),
        field=(
            f"layers[{index}].content.background_color"
        ),
    )

    _validate_optional_color(
        content.get("stroke_color"),
        field=f"layers[{index}].content.stroke_color",
    )

    _number_in_range(
        content.get(
            "stroke_width",
            0,
        ),
        minimum=0,
        maximum=20,
        field=f"layers[{index}].content.stroke_width",
    )

    shadow = content.get("shadow")

    if shadow is not None:
        _validate_shadow(
            shadow,
            index=index,
        )

    entities = content.get(
        "entities",
        [],
    )

    _validate_text_entities(
        entities,
        text=text,
        index=index,
    )


def _validate_shadow(
    shadow,
    *,
    index: int,
) -> None:
    if not isinstance(shadow, Mapping):
        raise ValidationError(
            {
                "layers": (
                    f"Text shadow at layer {index} "
                    "must be an object."
                ),
            }
        )

    _validate_optional_color(
        shadow.get("color"),
        field=f"layers[{index}].content.shadow.color",
        required=True,
    )

    _number_in_range(
        shadow.get(
            "radius",
            0,
        ),
        minimum=0,
        maximum=60,
        field=f"layers[{index}].content.shadow.radius",
    )

    _number_in_range(
        shadow.get(
            "offset_x",
            0,
        ),
        minimum=-100,
        maximum=100,
        field=f"layers[{index}].content.shadow.offset_x",
    )

    _number_in_range(
        shadow.get(
            "offset_y",
            0,
        ),
        minimum=-100,
        maximum=100,
        field=f"layers[{index}].content.shadow.offset_y",
    )


def _validate_text_entities(
    entities,
    *,
    text: str,
    index: int,
) -> None:
    if not isinstance(entities, list):
        raise ValidationError(
            {
                "layers": (
                    f"Entities at text layer {index} "
                    "must be a list."
                ),
            }
        )

    if len(entities) > MAX_ENTITIES_PER_TEXT:
        raise ValidationError(
            {
                "layers": (
                    f"Text layer {index} contains too "
                    "many entities."
                ),
            }
        )

    for entity_index, entity in enumerate(entities):
        if not isinstance(entity, Mapping):
            raise ValidationError(
                {
                    "layers": (
                        f"Entity {entity_index} at layer "
                        f"{index} must be an object."
                    ),
                }
            )

        entity_type = entity.get("type")

        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise ValidationError(
                {
                    "layers": (
                        f"Invalid entity type at layer {index}."
                    ),
                }
            )

        start = entity.get("start")
        length = entity.get("length")

        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 0
        ):
            raise ValidationError(
                {
                    "layers": (
                        f"Invalid entity start at layer {index}."
                    ),
                }
            )

        if (
            isinstance(length, bool)
            or not isinstance(length, int)
            or length <= 0
        ):
            raise ValidationError(
                {
                    "layers": (
                        f"Invalid entity length at layer {index}."
                    ),
                }
            )

        if start + length > len(text):
            raise ValidationError(
                {
                    "layers": (
                        f"Entity range exceeds text at "
                        f"layer {index}."
                    ),
                }
            )

        # Current phase keeps entities empty.
        # Resolved mentions and hashtags are enabled later.
        resolved = entity.get(
            "resolved",
            False,
        )

        if not isinstance(resolved, bool):
            raise ValidationError(
                {
                    "layers": (
                        f"Entity resolved flag at layer "
                        f"{index} must be boolean."
                    ),
                }
            )


def _validate_sticker_content(
    content,
    *,
    index: int,
) -> None:
    if not isinstance(content, Mapping):
        raise ValidationError(
            {
                "layers": (
                    f"Sticker layer {index} content must "
                    "be an object."
                ),
            }
        )

    sticker_id = str(
        content.get("sticker_id") or ""
    ).strip()

    try:
        uuid.UUID(sticker_id)
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(
            {
                "layers": (
                    f"Sticker layer {index} requires "
                    "a valid sticker_id."
                ),
            }
        )

    # External sticker URLs are forbidden.
    for forbidden_key in (
        "url",
        "image_url",
        "source_url",
        "asset_url",
    ):
        if content.get(forbidden_key):
            raise ValidationError(
                {
                    "layers": (
                        f"Sticker layer {index} cannot "
                        "contain an external URL."
                    ),
                }
            )


def _validate_optional_color(
    value,
    *,
    field: str,
    required: bool = False,
) -> None:
    if value in {
        None,
        "",
    }:
        if required:
            raise ValidationError(
                {
                    field: "Color is required.",
                }
            )

        return

    if (
        not isinstance(value, str)
        or not HEX_COLOR_PATTERN.fullmatch(value)
    ):
        raise ValidationError(
            {
                field: (
                    "Color must use #RRGGBB or "
                    "#RRGGBBAA format."
                ),
            }
        )


def _positive_integer(
    value,
    *,
    field: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValidationError(
            {
                field: "Value must be a positive integer.",
            }
        )

    return value


def _number_in_range(
    value,
    *,
    minimum: float,
    maximum: float,
    field: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise ValidationError(
            {
                field: "Value must be numeric.",
            }
        )

    numeric = float(value)

    if not minimum <= numeric <= maximum:
        raise ValidationError(
            {
                field: (
                    f"Value must be between "
                    f"{minimum} and {maximum}."
                ),
            }
        )

    return numeric