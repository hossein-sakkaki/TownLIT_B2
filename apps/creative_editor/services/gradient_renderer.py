# apps/creative_editor/services/gradient_renderer.py

from __future__ import annotations

import math

from PIL import (
    Image,
    ImageColor,
)


GRADIENT_STRIP_RESOLUTION = 4096
GRADIENT_EXTENDED_MIN = -0.25
GRADIENT_EXTENDED_MAX = 1.25


def parse_gradient_color(
    value,
    *,
    default: str = "#000000FF",
) -> tuple[int, int, int, int]:
    """
    Parse one #RRGGBB or #RRGGBBAA color.
    """

    raw = str(value or default).strip()

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


def interpolate_color(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    ratio: float,
) -> tuple[int, int, int, int]:
    """
    Interpolate two RGBA colors.
    """

    safe_ratio = max(
        0.0,
        min(
            1.0,
            float(ratio),
        ),
    )

    return tuple(
        int(
            round(
                start[channel]
                + (
                    end[channel]
                    - start[channel]
                )
                * safe_ratio
            )
        )
        for channel in range(4)
    )


def resolve_gradient_color(
    *,
    colors: list[tuple[int, int, int, int]],
    position: float,
) -> tuple[int, int, int, int]:
    """
    Resolve one multi-stop gradient color.
    """

    if not colors:
        return (
            0,
            0,
            0,
            255,
        )

    if len(colors) == 1:
        return colors[0]

    safe_position = max(
        0.0,
        min(
            1.0,
            float(position),
        ),
    )

    segment_count = len(colors) - 1
    scaled_position = safe_position * segment_count

    segment_index = min(
        segment_count - 1,
        int(
            math.floor(
                scaled_position
            )
        ),
    )

    local_ratio = (
        scaled_position
        - segment_index
    )

    return interpolate_color(
        colors[segment_index],
        colors[segment_index + 1],
        local_ratio,
    )


def build_gradient_strip(
    *,
    length: int,
    colors: list,
    minimum_position: float = 0.0,
    maximum_position: float = 1.0,
) -> Image.Image:
    """
    Build one high-resolution horizontal multi-stop strip.
    """

    safe_length = max(
        2,
        int(length),
    )

    parsed_colors = [
        parse_gradient_color(color)
        for color in colors
    ]

    if len(parsed_colors) < 2:
        parsed_colors = [
            parse_gradient_color(
                "#000000FF"
            ),
            parse_gradient_color(
                "#FFFFFFFF"
            ),
        ]

    minimum_position = float(
        minimum_position
    )

    maximum_position = float(
        maximum_position
    )

    if not math.isfinite(
        minimum_position
    ):
        minimum_position = 0.0

    if not math.isfinite(
        maximum_position
    ):
        maximum_position = 1.0

    if (
        maximum_position
        <= minimum_position
    ):
        minimum_position = 0.0
        maximum_position = 1.0

    image = Image.new(
        "RGBA",
        (
            safe_length,
            2,
        ),
    )

    pixels = image.load()

    position_span = (
        maximum_position
        - minimum_position
    )

    for x in range(safe_length):
        ratio = (
            x
            / max(
                1,
                safe_length - 1,
            )
        )

        position = (
            minimum_position
            + ratio * position_span
        )

        color = resolve_gradient_color(
            colors=parsed_colors,
            position=position,
        )

        pixels[x, 0] = color
        pixels[x, 1] = color

    return image


def normalized_gradient_angle(
    angle: float,
) -> float:
    """
    Normalize one gradient angle in degrees.
    """

    try:
        value = float(angle)
    except (
        TypeError,
        ValueError,
    ):
        return 0.0

    if not math.isfinite(value):
        return 0.0

    value = math.fmod(
        value,
        360.0,
    )

    if value > 180.0:
        value -= 360.0

    elif value < -180.0:
        value += 360.0

    return value


def build_linear_gradient(
    *,
    width: int,
    height: int,
    colors: list,
    angle: float,
) -> Image.Image:
    """
    Render a linear gradient using the same vector geometry
    as CreativeCanvasBackgroundView on iOS.

    The gradient is projected directly into final canvas
    coordinates. No bitmap rotation or post-rotation crop
    is performed.
    """

    safe_width = max(
        1,
        int(width),
    )

    safe_height = max(
        1,
        int(height),
    )

    angle_degrees = (
        normalized_gradient_angle(
            angle
        )
    )

    angle_radians = math.radians(
        angle_degrees
    )

    direction_x = math.cos(
        angle_radians
    )

    direction_y = math.sin(
        angle_radians
    )

    strip = build_gradient_strip(
        length=(
            GRADIENT_STRIP_RESOLUTION
        ),
        colors=colors,
        minimum_position=(
            GRADIENT_EXTENDED_MIN
        ),
        maximum_position=(
            GRADIENT_EXTENDED_MAX
        ),
    )

    strip_span = (
        GRADIENT_EXTENDED_MAX
        - GRADIENT_EXTENDED_MIN
    )

    strip_max_x = float(
        strip.width - 1
    )

    x_denominator = max(
        1,
        safe_width - 1,
    )

    y_denominator = max(
        1,
        safe_height - 1,
    )

    source_scale = (
        strip_max_x
        / strip_span
    )

    coefficient_x = (
        source_scale
        * direction_x
        / x_denominator
    )

    coefficient_y = (
        source_scale
        * direction_y
        / y_denominator
    )

    offset = source_scale * (
        0.5
        - 0.5 * direction_x
        - 0.5 * direction_y
        - GRADIENT_EXTENDED_MIN
    )

    return strip.transform(
        (
            safe_width,
            safe_height,
        ),
        Image.Transform.AFFINE,
        (
            coefficient_x,
            coefficient_y,
            offset,
            0.0,
            0.0,
            0.5,
        ),
        resample=(
            Image.Resampling.BICUBIC
        ),
    ).convert(
        "RGBA"
    )