# apps/creative_editor/services/mixed_text_renderer.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-07-21.
# Last Update by Hossein Sakkaki on 2026-08-10.

from __future__ import annotations

import math
import unicodedata

from dataclasses import dataclass

from PIL import (
    Image,
    ImageDraw,
    ImageFilter,
)

from apps.creative_editor.services.emoji_text import (
    CreativeTextCluster,
    build_text_clusters,
)
from apps.creative_editor.services.font_coverage import (
    CreativeFontCoverageError,
    font_supports_text,
    resolve_compatible_font_key,
)
from apps.creative_editor.services.font_resolver import (
    ResolvedCreativeEmojiFont,
    ResolvedCreativeFont,
    load_creative_emoji_font,
    load_creative_font,
)


@dataclass(frozen=True)
class CreativeTextRun:
    """
    One contiguous text or Emoji run.
    """

    text: str
    is_emoji: bool
    font_key: str | None = None


@dataclass(frozen=True)
class CreativeMeasuredRun:
    """
    One measured render run.
    """

    run: CreativeTextRun
    width: int
    font: ResolvedCreativeFont | None
    ascent: int
    descent: int


@dataclass(frozen=True)
class CreativeTextLine:
    """
    One wrapped visual line.
    """

    runs: tuple[CreativeMeasuredRun, ...]
    width: int
    height: int
    ascent: int
    descent: int
    direction: str


@dataclass(frozen=True)
class CreativeTextLayout:
    """
    Final multiline layout.
    """

    lines: tuple[CreativeTextLine, ...]
    width: int
    height: int


@dataclass(frozen=True)
class CreativeTextRenderOptions:
    """
    Immutable text render options.
    """

    box_width: int
    box_height: int
    alignment: str
    direction: str
    spacing: int
    text_color: tuple[int, int, int, int]
    stroke_color: tuple[int, int, int, int]
    stroke_width: int
    shadow: dict | None


class CreativeMixedTextRenderer:
    """
    Render mixed text using verified Creative Fonts.

    The selected font remains primary. Unsupported text
    clusters use compatible bundled TownLIT fonts.
    Emoji continues through the dedicated Emoji renderer.
    """

    def __init__(
        self,
        *,
        text_font: ResolvedCreativeFont,
    ):
        self.text_font = text_font

        self.emoji_font: ResolvedCreativeEmojiFont = (
            load_creative_emoji_font(
                size=text_font.size
            )
        )

        self._resolved_fonts: dict[str, ResolvedCreativeFont] = {
            text_font.key: text_font,
        }

        self._measurement_surface = Image.new(
            "RGBA",
            (8, 8),
            (0, 0, 0, 0),
        )

        self._measurement_draw = ImageDraw.Draw(
            self._measurement_surface
        )

        self.emoji_visual_height = max(
            8,
            int(round(self.text_font.size * 1.04)),
        )

    def render(
        self,
        *,
        text: str,
        options: CreativeTextRenderOptions,
    ) -> Image.Image:
        layer = Image.new(
            "RGBA",
            (
                max(1, options.box_width),
                max(1, options.box_height),
            ),
            (0, 0, 0, 0),
        )

        max_text_width = max(
            1,
            options.box_width - options.stroke_width * 2,
        )

        layout = self._build_layout(
            text=text,
            max_width=max_text_width,
            spacing=options.spacing,
            requested_direction=options.direction,
        )

        origin_y = max(
            0,
            (options.box_height - layout.height) // 2,
        )

        if isinstance(options.shadow, dict):
            self._render_shadow(
                target=layer,
                layout=layout,
                options=options,
                origin_y=origin_y,
            )

        self._render_layout(
            target=layer,
            layout=layout,
            options=options,
            origin_y=origin_y,
            shadow_color=None,
        )

        return layer

    # MARK: - Layout

    def _build_layout(
        self,
        *,
        text: str,
        max_width: int,
        spacing: int,
        requested_direction: str,
    ) -> CreativeTextLayout:
        paragraphs = text.split("\n")
        lines: list[CreativeTextLine] = []

        for paragraph in paragraphs:
            paragraph_direction = self._resolve_direction(
                requested=requested_direction,
                text=paragraph,
            )

            if paragraph == "":
                lines.append(
                    self._build_line(
                        clusters=[],
                        direction=paragraph_direction,
                    )
                )
                continue

            clusters = build_text_clusters(
                paragraph
            )

            wrapped = self._wrap_clusters(
                clusters=clusters,
                max_width=max_width,
                direction=paragraph_direction,
            )

            for line_clusters in wrapped:
                lines.append(
                    self._build_line(
                        clusters=line_clusters,
                        direction=paragraph_direction,
                    )
                )

        if not lines:
            lines.append(
                self._build_line(
                    clusters=[],
                    direction="ltr",
                )
            )

        total_height = sum(
            line.height
            for line in lines
        )

        if len(lines) > 1:
            total_height += (
                max(0, spacing)
                * (len(lines) - 1)
            )

        return CreativeTextLayout(
            lines=tuple(lines),
            width=max(
                (line.width for line in lines),
                default=1,
            ),
            height=max(1, total_height),
        )

    def _wrap_clusters(
        self,
        *,
        clusters: list[CreativeTextCluster],
        max_width: int,
        direction: str,
    ) -> list[list[CreativeTextCluster]]:
        if not clusters:
            return [[]]

        output: list[list[CreativeTextCluster]] = []
        current: list[CreativeTextCluster] = []

        for cluster in clusters:
            candidate = [*current, cluster]

            width = self._measure_clusters(
                candidate,
                direction=direction,
            )

            if width <= max_width or not current:
                current = candidate
                continue

            break_index = self._last_break_index(
                current
            )

            if break_index is not None:
                head = current[:break_index]
                tail = current[break_index + 1:]

                if head:
                    output.append(
                        self._trim_trailing_whitespace(
                            head
                        )
                    )

                current = self._trim_leading_whitespace(
                    [*tail, cluster]
                )

                if (
                    current
                    and self._measure_clusters(
                        current,
                        direction=direction,
                    ) > max_width
                ):
                    current = self._split_oversized_clusters(
                        clusters=current,
                        output=output,
                        max_width=max_width,
                        direction=direction,
                    )

                continue

            output.append(
                self._trim_trailing_whitespace(
                    current
                )
            )

            current = self._trim_leading_whitespace(
                [cluster]
            )

        if current:
            output.append(
                self._trim_trailing_whitespace(
                    current
                )
            )

        return output or [[]]

    def _split_oversized_clusters(
        self,
        *,
        clusters: list[CreativeTextCluster],
        output: list[list[CreativeTextCluster]],
        max_width: int,
        direction: str,
    ) -> list[CreativeTextCluster]:
        current: list[CreativeTextCluster] = []

        for cluster in clusters:
            candidate = [*current, cluster]

            width = self._measure_clusters(
                candidate,
                direction=direction,
            )

            if width <= max_width or not current:
                current = candidate
                continue

            output.append(
                self._trim_trailing_whitespace(
                    current
                )
            )

            current = self._trim_leading_whitespace(
                [cluster]
            )

        return current

    @staticmethod
    def _last_break_index(
        clusters: list[CreativeTextCluster],
    ) -> int | None:
        for index in range(
            len(clusters) - 1,
            -1,
            -1,
        ):
            if clusters[index].text.isspace():
                return index

        return None

    @staticmethod
    def _trim_leading_whitespace(
        clusters: list[CreativeTextCluster],
    ) -> list[CreativeTextCluster]:
        index = 0

        while (
            index < len(clusters)
            and clusters[index].text.isspace()
        ):
            index += 1

        return clusters[index:]

    @staticmethod
    def _trim_trailing_whitespace(
        clusters: list[CreativeTextCluster],
    ) -> list[CreativeTextCluster]:
        index = len(clusters)

        while (
            index > 0
            and clusters[index - 1].text.isspace()
        ):
            index -= 1

        return clusters[:index]

    def _build_line(
        self,
        *,
        clusters: list[CreativeTextCluster],
        direction: str,
    ) -> CreativeTextLine:
        runs = self._build_runs(
            clusters
        )

        measured_runs = [
            self._measure_run(
                run,
                direction=direction,
            )
            for run in runs
        ]

        if direction == "rtl":
            measured_runs.reverse()

        line_width = sum(
            item.width
            for item in measured_runs
        )

        default_ascent, default_descent = (
            self.text_font.font.getmetrics()
        )

        line_ascent = max(
            [
                int(default_ascent),
                int(
                    round(
                        self.emoji_visual_height * 0.86
                    )
                ),
                *[
                    item.ascent
                    for item in measured_runs
                ],
            ]
        )

        line_descent = max(
            [
                int(default_descent),
                self.emoji_visual_height - line_ascent,
                *[
                    item.descent
                    for item in measured_runs
                ],
            ]
        )

        line_descent = max(
            0,
            line_descent,
        )

        return CreativeTextLine(
            runs=tuple(measured_runs),
            width=max(0, line_width),
            height=max(
                1,
                line_ascent + line_descent,
            ),
            ascent=line_ascent,
            descent=line_descent,
            direction=direction,
        )

    # MARK: - Font Runs

    def _build_runs(
        self,
        clusters: list[CreativeTextCluster],
    ) -> list[CreativeTextRun]:
        if not clusters:
            return []

        output: list[CreativeTextRun] = []

        current_text = ""
        current_is_emoji: bool | None = None
        current_font_key: str | None = None

        def flush() -> None:
            nonlocal current_text
            nonlocal current_is_emoji
            nonlocal current_font_key

            if not current_text:
                return

            output.append(
                CreativeTextRun(
                    text=current_text,
                    is_emoji=bool(current_is_emoji),
                    font_key=current_font_key,
                )
            )

            current_text = ""
            current_is_emoji = None
            current_font_key = None

        for cluster in clusters:
            if cluster.is_emoji:
                run_is_emoji = True
                run_font_key = None

            elif cluster.text.isspace():
                run_is_emoji = False
                run_font_key = (
                    current_font_key
                    if current_is_emoji is False
                    and current_font_key
                    else self.text_font.key
                )

            else:
                run_is_emoji = False
                run_font_key = self._font_key_for_text(
                    cluster.text
                )

            same_renderer = (
                current_is_emoji == run_is_emoji
                and current_font_key == run_font_key
            )

            if (
                current_is_emoji is None
                or same_renderer
            ):
                current_text += cluster.text
                current_is_emoji = run_is_emoji
                current_font_key = run_font_key
                continue

            flush()

            current_text = cluster.text
            current_is_emoji = run_is_emoji
            current_font_key = run_font_key

        flush()

        return output

    def _font_key_for_text(
        self,
        text: str,
    ) -> str:
        if font_supports_text(
            font_key=self.text_font.key,
            text=text,
        ):
            return self.text_font.key

        return resolve_compatible_font_key(
            text=text,
            preferred_font_key=self.text_font.key,
        )

    def _font_for_key(
        self,
        font_key: str,
    ) -> ResolvedCreativeFont:
        cached = self._resolved_fonts.get(
            font_key
        )

        if cached is not None:
            return cached

        resolved = load_creative_font(
            font_key=font_key,
            size=self.text_font.size,
        )

        self._resolved_fonts[
            font_key
        ] = resolved

        return resolved

    # MARK: - Measurement

    def _measure_clusters(
        self,
        clusters: list[CreativeTextCluster],
        *,
        direction: str,
    ) -> int:
        return sum(
            self._measure_run(
                run,
                direction=direction,
            ).width
            for run in self._build_runs(
                clusters
            )
        )

    def _measure_run(
        self,
        run: CreativeTextRun,
        *,
        direction: str,
    ) -> CreativeMeasuredRun:
        if not run.text:
            return CreativeMeasuredRun(
                run=run,
                width=0,
                font=None,
                ascent=0,
                descent=0,
            )

        if run.is_emoji:
            width = self._measure_emoji_run(
                run.text
            )

            ascent = int(
                round(
                    self.emoji_visual_height * 0.86
                )
            )

            return CreativeMeasuredRun(
                run=run,
                width=width,
                font=None,
                ascent=ascent,
                descent=max(
                    0,
                    self.emoji_visual_height - ascent,
                ),
            )

        if not run.font_key:
            raise CreativeFontCoverageError(
                "A non-Emoji text run has no font key."
            )

        resolved_font = self._font_for_key(
            run.font_key
        )

        bbox = self._measurement_draw.textbbox(
            (0, 0),
            run.text,
            font=resolved_font.font,
            direction=direction,
        )

        ascent, descent = (
            resolved_font.font.getmetrics()
        )

        return CreativeMeasuredRun(
            run=run,
            width=max(
                0,
                int(
                    math.ceil(
                        bbox[2] - bbox[0]
                    )
                ),
            ),
            font=resolved_font,
            ascent=max(1, int(ascent)),
            descent=max(0, int(descent)),
        )

    def _measure_emoji_run(
        self,
        text: str,
    ) -> int:
        return self._render_emoji_run(
            text
        ).width

    # MARK: - Drawing

    def _render_layout(
        self,
        *,
        target: Image.Image,
        layout: CreativeTextLayout,
        options: CreativeTextRenderOptions,
        origin_y: int,
        shadow_color: tuple[int, int, int, int] | None,
        origin_x_offset: int = 0,
    ) -> None:
        current_y = origin_y
        draw = ImageDraw.Draw(
            target
        )

        for line in layout.lines:
            line_x = (
                self._aligned_line_x(
                    alignment=options.alignment,
                    box_width=options.box_width,
                    line_width=line.width,
                )
                + origin_x_offset
            )

            current_x = line_x

            for measured in line.runs:
                run = measured.run

                if run.is_emoji:
                    emoji_image = self._render_emoji_run(
                        run.text
                    )

                    if shadow_color is not None:
                        emoji_image = self._colorize_alpha(
                            emoji_image,
                            shadow_color,
                        )

                    emoji_y = (
                        current_y
                        + line.ascent
                        - emoji_image.height
                    )

                    target.alpha_composite(
                        emoji_image,
                        (
                            int(current_x),
                            int(emoji_y),
                        ),
                    )

                else:
                    if measured.font is None:
                        raise CreativeFontCoverageError(
                            "A text run has no resolved font."
                        )

                    text_y = (
                        current_y
                        + line.ascent
                        - measured.ascent
                    )

                    fill = (
                        shadow_color
                        if shadow_color is not None
                        else options.text_color
                    )

                    draw.text(
                        (
                            int(current_x),
                            int(text_y),
                        ),
                        run.text,
                        font=measured.font.font,
                        fill=fill,
                        direction=line.direction,
                        stroke_width=(
                            0
                            if shadow_color is not None
                            else options.stroke_width
                        ),
                        stroke_fill=(
                            None
                            if shadow_color is not None
                            else options.stroke_color
                        ),
                    )

                current_x += measured.width

            current_y += (
                line.height
                + max(0, options.spacing)
            )

    def _render_shadow(
        self,
        *,
        target: Image.Image,
        layout: CreativeTextLayout,
        options: CreativeTextRenderOptions,
        origin_y: int,
    ) -> None:
        shadow = options.shadow or {}

        shadow_layer = Image.new(
            "RGBA",
            target.size,
            (0, 0, 0, 0),
        )

        offset_x = int(
            round(
                float(
                    shadow.get(
                        "offset_x",
                        0,
                    )
                )
            )
        )

        offset_y = int(
            round(
                float(
                    shadow.get(
                        "offset_y",
                        0,
                    )
                )
            )
        )

        radius = max(
            0,
            float(
                shadow.get(
                    "radius",
                    0,
                )
            ),
        )

        shadow_color = self._parse_shadow_color(
            shadow.get(
                "color",
                "#00000088",
            )
        )

        self._render_layout(
            target=shadow_layer,
            layout=layout,
            options=options,
            origin_y=origin_y + offset_y,
            shadow_color=shadow_color,
            origin_x_offset=offset_x,
        )

        if radius > 0:
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(
                    radius=radius
                )
            )

        target.alpha_composite(
            shadow_layer
        )

    # MARK: - Emoji

    def _render_emoji_run(
        self,
        text: str,
    ) -> Image.Image:
        padding = 20

        raw_bbox = self._measurement_draw.textbbox(
            (0, 0),
            text,
            font=self.emoji_font.font,
        )

        raw_width = max(
            1,
            raw_bbox[2] - raw_bbox[0],
        )

        raw_height = max(
            1,
            raw_bbox[3] - raw_bbox[1],
        )

        surface = Image.new(
            "RGBA",
            (
                raw_width + padding * 2,
                raw_height + padding * 2,
            ),
            (0, 0, 0, 0),
        )

        draw = ImageDraw.Draw(
            surface
        )

        draw.text(
            (
                padding - raw_bbox[0],
                padding - raw_bbox[1],
            ),
            text,
            font=self.emoji_font.font,
            embedded_color=True,
        )

        alpha = surface.getchannel(
            "A"
        )

        crop_box = alpha.getbbox()

        if crop_box is None:
            size = max(
                1,
                self.emoji_visual_height,
            )

            return Image.new(
                "RGBA",
                (size, size),
                (0, 0, 0, 0),
            )

        cropped = surface.crop(
            crop_box
        )

        target_height = max(
            1,
            self.emoji_visual_height,
        )

        scale = (
            target_height
            / max(1, cropped.height)
        )

        target_width = max(
            1,
            int(
                round(
                    cropped.width * scale
                )
            ),
        )

        return cropped.resize(
            (
                target_width,
                target_height,
            ),
            resample=Image.Resampling.LANCZOS,
        )

    @staticmethod
    def _colorize_alpha(
        image: Image.Image,
        color: tuple[int, int, int, int],
    ) -> Image.Image:
        alpha = image.getchannel(
            "A"
        )

        color_alpha = max(
            0,
            min(
                255,
                int(color[3]),
            ),
        )

        if color_alpha < 255:
            alpha = alpha.point(
                lambda value: int(
                    value * color_alpha / 255
                )
            )

        result = Image.new(
            "RGBA",
            image.size,
            (
                color[0],
                color[1],
                color[2],
                0,
            ),
        )

        result.putalpha(
            alpha
        )

        return result

    # MARK: - Direction

    @staticmethod
    def _resolve_direction(
        *,
        requested: str,
        text: str,
    ) -> str:
        if requested == "rtl":
            return "rtl"

        if requested == "ltr":
            return "ltr"

        for character in text:
            bidi_class = unicodedata.bidirectional(
                character
            )

            if bidi_class in {
                "R",
                "AL",
                "AN",
            }:
                return "rtl"

            if bidi_class == "L":
                return "ltr"

        return "ltr"

    # MARK: - Alignment

    @staticmethod
    def _aligned_line_x(
        *,
        alignment: str,
        box_width: int,
        line_width: int,
    ) -> int:
        if alignment == "leading":
            return 0

        if alignment == "trailing":
            return max(
                0,
                box_width - line_width,
            )

        return max(
            0,
            (box_width - line_width) // 2,
        )

    # MARK: - Color

    @staticmethod
    def _parse_shadow_color(
        value,
    ) -> tuple[int, int, int, int]:
        from PIL import ImageColor

        raw = str(
            value or "#00000088"
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
                "#00000088",
                "RGBA",
            )