# apps/creative_editor/services/gradient_renderer.py

from __future__ import annotations

import math

from PIL import (
    Image,
    ImageColor,
    ImageOps,
)


def parse_gradient_color(
    value,
    *,
    default: str = "#000000FF",
) -> tuple[int, int, int, int]:
    """
    Parse one RGBA color.
    """

    raw = str(
        value or default
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


def build_gradient_strip(
    *,
    length: int,
    colors: list,
) -> Image.Image:
    """
    Build one horizontal multi-stop strip.
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

    image = Image.new(
        "RGBA",
        (
            safe_length,
            1,
        ),
    )

    pixels = image.load()

    segment_count = (
        len(parsed_colors) - 1
    )

    for x in range(safe_length):
        global_ratio = (
            x
            / max(
                1,
                safe_length - 1,
            )
        )

        scaled_ratio = (
            global_ratio
            * segment_count
        )

        segment_index = min(
            segment_count - 1,
            int(
                math.floor(
                    scaled_ratio
                )
            ),
        )

        local_ratio = (
            scaled_ratio
            - segment_index
        )

        pixels[x, 0] = (
            interpolate_color(
                parsed_colors[
                    segment_index
                ],
                parsed_colors[
                    segment_index + 1
                ],
                local_ratio,
            )
        )

    return image


def build_linear_gradient(
    *,
    width: int,
    height: int,
    colors: list,
    angle: float,
) -> Image.Image:
    """
    Build an efficient angled gradient.
    """

    safe_width = max(
        1,
        int(width),
    )

    safe_height = max(
        1,
        int(height),
    )

    diagonal = max(
        2,
        int(
            math.ceil(
                math.hypot(
                    safe_width,
                    safe_height,
                )
            )
        ),
    )

    strip = build_gradient_strip(
        length=diagonal,
        colors=colors,
    )

    gradient = strip.resize(
        (
            diagonal,
            diagonal,
        ),
        resample=Image.Resampling.BILINEAR,
    )

    rotated = gradient.rotate(
        -float(angle),
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )

    return ImageOps.fit(
        rotated,
        (
            safe_width,
            safe_height,
        ),
        method=Image.Resampling.LANCZOS,
        centering=(
            0.5,
            0.5,
        ),
    )