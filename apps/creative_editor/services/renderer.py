# apps/creative_editor/services/renderer.py

from __future__ import annotations

import logging
import math
import uuid

from dataclasses import dataclass
from typing import Callable

from PIL import (
    Image,
    ImageColor,
    ImageDraw,
    ImageOps,
)

from apps.creative_editor.constants import (
    CREATIVE_RENDER_DEFAULT_BACKGROUND,
    CREATIVE_RENDER_MAX_CANVAS_PIXELS,
)
from apps.creative_editor.models import (
    CreativeComposition,
)
from apps.creative_editor.services.asset_loader import (
    load_composition_source,
    load_sticker_asset,
)
from apps.creative_editor.services.font_resolver import (
    load_creative_font,
)
from apps.creative_editor.services.gradient_renderer import (
    build_linear_gradient,
)
from apps.creative_editor.services.mixed_text_renderer import (
    CreativeMixedTextRenderer,
    CreativeTextRenderOptions,
)
from apps.creative_editor.services.render_resources import (
    CreativeRenderResources,
    resolve_render_resources,
)


logger = logging.getLogger(__name__)


class CreativeRenderError(Exception):
    """
    Raised when composition rendering fails.
    """


@dataclass(frozen=True)
class CreativeRenderContext:
    """
    Immutable render input.
    """

    composition: CreativeComposition
    document: dict
    revision: int


ProgressCallback = Callable[
    [int, str, str],
    None,
]


def noop_progress(
    progress: int,
    stage: str,
    message: str,
) -> None:
    """
    Default progress callback.
    """

    return


def parse_color(
    value,
    *,
    default: str = "#00000000",
) -> tuple[int, int, int, int]:
    """
    Parse #RRGGBB or #RRGGBBAA.
    """

    raw = str(
        value
        or default
    ).strip()

    if len(raw) == 7:
        raw = f"{raw}FF"

    try:
        return ImageColor.getcolor(
            raw,
            "RGBA",
        )

    except Exception:
        return ImageColor.getcolor(
            default,
            "RGBA",
        )


def normalized_box(
    *,
    transform: dict,
    canvas_width: int,
    canvas_height: int,
) -> tuple[int, int, int, int]:
    """
    Convert normalized transform into a pixel box.
    """

    center_x = float(
        transform.get(
            "center_x",
            0.5,
        )
    )

    center_y = float(
        transform.get(
            "center_y",
            0.5,
        )
    )

    normalized_width = float(
        transform.get(
            "width",
            0.25,
        )
    )

    normalized_height = float(
        transform.get(
            "height",
            0.25,
        )
    )

    scale = float(
        transform.get(
            "scale",
            1,
        )
    )

    width = max(
        1,
        int(
            round(
                canvas_width
                * normalized_width
                * scale
            )
        ),
    )

    height = max(
        1,
        int(
            round(
                canvas_height
                * normalized_height
                * scale
            )
        ),
    )

    center_pixel_x = int(
        round(
            canvas_width
            * center_x
        )
    )

    center_pixel_y = int(
        round(
            canvas_height
            * center_y
        )
    )

    left = (
        center_pixel_x
        - width // 2
    )

    top = (
        center_pixel_y
        - height // 2
    )

    return (
        left,
        top,
        width,
        height,
    )


def apply_layer_opacity(
    image: Image.Image,
    opacity: float,
) -> Image.Image:
    """
    Apply layer opacity to RGBA content.
    """

    safe_opacity = max(
        0.0,
        min(
            1.0,
            float(opacity),
        ),
    )

    if safe_opacity >= 1:
        return image

    result = image.copy()

    alpha = result.getchannel(
        "A"
    )

    alpha = alpha.point(
        lambda value: int(
            value
            * safe_opacity
        )
    )

    result.putalpha(
        alpha
    )

    return result


def fit_image_cover(
    image: Image.Image,
    *,
    width: int,
    height: int,
) -> Image.Image:
    """
    Resize and crop an image to cover the canvas.
    """

    return ImageOps.fit(
        image.convert(
            "RGBA"
        ),
        (
            width,
            height,
        ),
        method=Image.Resampling.LANCZOS,
        centering=(
            0.5,
            0.5,
        ),
    )


class CreativeCompositionRenderer:
    """
    Render a versioned CreativeComposition document.
    """

    def render(
        self,
        *,
        context: CreativeRenderContext,
        progress_callback: ProgressCallback = noop_progress,
    ) -> Image.Image:
        """
        Render one immutable document snapshot.
        """

        document = (
            context.document
            or {}
        )

        resources = (
            resolve_render_resources(
                document
            )
        )

        canvas = (
            document.get(
                "canvas"
            )
            or {}
        )

        width = int(
            canvas.get(
                "width",
                context.composition.canvas_width,
            )
        )

        height = int(
            canvas.get(
                "height",
                context.composition.canvas_height,
            )
        )

        self._validate_canvas_size(
            width=width,
            height=height,
        )

        progress_callback(
            10,
            "background",
            "Preparing background",
        )

        output = self._render_background(
            composition=context.composition,
            canvas=canvas,
            width=width,
            height=height,
        )

        layers = (
            document.get(
                "layers"
            )
            or []
        )

        visible_layers = [
            layer
            for layer in layers
            if (
                isinstance(
                    layer,
                    dict,
                )
                and not layer.get(
                    "is_hidden",
                    False,
                )
            )
        ]

        visible_layers.sort(
            key=lambda layer: (
                int(
                    layer.get(
                        "z_index",
                        0,
                    )
                ),
                str(
                    layer.get(
                        "id",
                        "",
                    )
                ),
            )
        )

        total_layers = max(
            1,
            len(
                visible_layers
            ),
        )

        for index, layer in enumerate(
            visible_layers
        ):
            layer_progress = (
                20
                + int(
                    (
                        index
                        / total_layers
                    )
                    * 65
                )
            )

            layer_type = (
                layer.get(
                    "type"
                )
            )

            progress_callback(
                layer_progress,
                "layers",
                (
                    f"Rendering {layer_type} "
                    f"layer {index + 1}"
                ),
            )

            if layer_type == "text":
                self._render_text_layer(
                    output=output,
                    layer=layer,
                )

            elif layer_type == "sticker":
                self._render_sticker_layer(
                    output=output,
                    layer=layer,
                    resources=resources,
                )

            else:
                raise CreativeRenderError(
                    (
                        "Unsupported render "
                        f"layer type: {layer_type!r}"
                    )
                )

        progress_callback(
            90,
            "finalizing",
            "Finalizing composition",
        )

        return output.convert(
            "RGBA"
        )

    def _validate_canvas_size(
        self,
        *,
        width: int,
        height: int,
    ) -> None:
        """
        Validate memory-sensitive canvas dimensions.
        """

        if (
            width <= 0
            or height <= 0
        ):
            raise CreativeRenderError(
                (
                    "Canvas dimensions "
                    "must be positive."
                )
            )

        if (
            width > 8192
            or height > 8192
        ):
            raise CreativeRenderError(
                (
                    "Canvas dimensions "
                    "exceed the render limit."
                )
            )

        if (
            width * height
            > CREATIVE_RENDER_MAX_CANVAS_PIXELS
        ):
            raise CreativeRenderError(
                (
                    "Canvas contains "
                    "too many pixels."
                )
            )

    def _render_background(
        self,
        *,
        composition: CreativeComposition,
        canvas: dict,
        width: int,
        height: int,
    ) -> Image.Image:
        """
        Render the canvas background.
        """

        background = (
            canvas.get(
                "background"
            )
            or {
                "type": "transparent",
            }
        )

        background_type = (
            background.get(
                "type",
                "transparent",
            )
        )

        if background_type == "transparent":
            return Image.new(
                "RGBA",
                (
                    width,
                    height,
                ),
                parse_color(
                    CREATIVE_RENDER_DEFAULT_BACKGROUND
                ),
            )

        if background_type == "color":
            return Image.new(
                "RGBA",
                (
                    width,
                    height,
                ),
                parse_color(
                    background.get(
                        "color"
                    ),
                    default="#000000FF",
                ),
            )

        if background_type == "gradient":
            return build_linear_gradient(
                width=width,
                height=height,
                colors=(
                    background.get(
                        "colors"
                    )
                    or [
                        "#000000FF",
                        "#FFFFFFFF",
                    ]
                ),
                angle=float(
                    background.get(
                        "angle",
                        0,
                    )
                ),
            )

        if background_type == "image":
            loaded = (
                load_composition_source(
                    composition
                )
            )

            if loaded is None:
                raise CreativeRenderError(
                    (
                        "Image background "
                        "source is unavailable."
                    )
                )

            return fit_image_cover(
                loaded.image,
                width=width,
                height=height,
            )

        raise CreativeRenderError(
            (
                "Unsupported canvas "
                f"background type: {background_type!r}"
            )
        )

    def _render_text_layer(
        self,
        *,
        output: Image.Image,
        layer: dict,
    ) -> None:
        """
        Render one mixed text and Emoji layer.
        """

        transform = (
            layer.get(
                "transform"
            )
            or {}
        )

        content = (
            layer.get(
                "content"
            )
            or {}
        )

        (
            left,
            top,
            box_width,
            box_height,
        ) = normalized_box(
            transform=transform,
            canvas_width=output.width,
            canvas_height=output.height,
        )

        text = str(
            content.get(
                "text",
                "",
            )
        )

        if not text:
            return

        resolved_font = (
            load_creative_font(
                font_key=str(
                    content.get(
                        "font_key",
                        "",
                    )
                ),
                size=float(
                    content.get(
                        "font_size",
                        48,
                    )
                ),
            )
        )

        text_renderer = (
            CreativeMixedTextRenderer(
                text_font=resolved_font
            )
        )

        layer_canvas = Image.new(
            "RGBA",
            (
                box_width,
                box_height,
            ),
            (
                0,
                0,
                0,
                0,
            ),
        )

        draw = ImageDraw.Draw(
            layer_canvas
        )

        background_color = (
            content.get(
                "background_color"
            )
        )

        if background_color:
            draw.rounded_rectangle(
                (
                    0,
                    0,
                    box_width,
                    box_height,
                ),
                radius=max(
                    0,
                    int(
                        min(
                            box_width,
                            box_height,
                        )
                        * 0.04
                    ),
                ),
                fill=parse_color(
                    background_color
                ),
            )

        text_color = parse_color(
            content.get(
                "color",
                "#FFFFFFFF",
            ),
            default="#FFFFFFFF",
        )

        stroke_color = parse_color(
            content.get(
                "stroke_color",
                "#00000000",
            )
        )

        stroke_width = max(
            0,
            int(
                round(
                    float(
                        content.get(
                            "stroke_width",
                            0,
                        )
                    )
                )
            ),
        )

        alignment = str(
            content.get(
                "alignment",
                "center",
            )
        )

        direction = str(
            content.get(
                "direction",
                "auto",
            )
        )

        spacing = int(
            round(
                float(
                    content.get(
                        "line_spacing",
                        0,
                    )
                )
            )
        )

        shadow = (
            content.get(
                "shadow"
            )
        )

        rendered_text = (
            text_renderer.render(
                text=text,
                options=CreativeTextRenderOptions(
                    box_width=box_width,
                    box_height=box_height,
                    alignment=alignment,
                    direction=direction,
                    spacing=spacing,
                    text_color=text_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    shadow=(
                        shadow
                        if isinstance(
                            shadow,
                            dict,
                        )
                        else None
                    ),
                ),
            )
        )

        layer_canvas.alpha_composite(
            rendered_text
        )

        self._composite_transformed_layer(
            output=output,
            layer_image=layer_canvas,
            layer=layer,
            left=left,
            top=top,
        )

    def _render_sticker_layer(
        self,
        *,
        output: Image.Image,
        layer: dict,
        resources: CreativeRenderResources,
    ) -> None:
        """
        Render one approved sticker layer.
        """

        transform = (
            layer.get(
                "transform"
            )
            or {}
        )

        content = (
            layer.get(
                "content"
            )
            or {}
        )

        raw_sticker_id = str(
            content.get(
                "sticker_id",
                "",
            )
        ).strip()

        try:
            sticker_id = str(
                uuid.UUID(
                    raw_sticker_id
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise CreativeRenderError(
                (
                    "Sticker layer contains "
                    "an invalid sticker identifier: "
                    f"{raw_sticker_id!r}"
                )
            ) from exc

        sticker = (
            resources.stickers.get(
                sticker_id
            )
        )

        if sticker is None:
            raise CreativeRenderError(
                (
                    "Sticker resource "
                    f"is unavailable: {sticker_id}"
                )
            )

        loaded = load_sticker_asset(
            sticker
        )

        (
            left,
            top,
            width,
            height,
        ) = normalized_box(
            transform=transform,
            canvas_width=output.width,
            canvas_height=output.height,
        )

        sticker_image = (
            ImageOps.contain(
                loaded.image,
                (
                    width,
                    height,
                ),
                method=(
                    Image.Resampling.LANCZOS
                ),
            )
        )

        layer_canvas = Image.new(
            "RGBA",
            (
                width,
                height,
            ),
            (
                0,
                0,
                0,
                0,
            ),
        )

        sticker_x = (
            width
            - sticker_image.width
        ) // 2

        sticker_y = (
            height
            - sticker_image.height
        ) // 2

        layer_canvas.alpha_composite(
            sticker_image,
            (
                sticker_x,
                sticker_y,
            ),
        )

        self._composite_transformed_layer(
            output=output,
            layer_image=layer_canvas,
            layer=layer,
            left=left,
            top=top,
        )

    def _composite_transformed_layer(
        self,
        *,
        output: Image.Image,
        layer_image: Image.Image,
        layer: dict,
        left: int,
        top: int,
    ) -> None:
        """
        Apply flip, rotation and opacity.
        """

        transform = (
            layer.get(
                "transform"
            )
            or {}
        )

        if transform.get(
            "flip_x",
            False,
        ):
            layer_image = (
                ImageOps.mirror(
                    layer_image
                )
            )

        if transform.get(
            "flip_y",
            False,
        ):
            layer_image = (
                ImageOps.flip(
                    layer_image
                )
            )

        opacity = float(
            layer.get(
                "opacity",
                1,
            )
        )

        layer_image = (
            apply_layer_opacity(
                layer_image,
                opacity,
            )
        )

        rotation_radians = float(
            transform.get(
                "rotation",
                0,
            )
        )

        rotation_degrees = (
            math.degrees(
                rotation_radians
            )
        )

        if (
            abs(rotation_degrees)
            > 0.001
        ):
            original_width = (
                layer_image.width
            )

            original_height = (
                layer_image.height
            )

            layer_image = (
                layer_image.rotate(
                    -rotation_degrees,
                    resample=(
                        Image.Resampling.BICUBIC
                    ),
                    expand=True,
                )
            )

            left -= (
                layer_image.width
                - original_width
            ) // 2

            top -= (
                layer_image.height
                - original_height
            ) // 2

        output.alpha_composite(
            layer_image,
            (
                int(left),
                int(top),
            ),
        )