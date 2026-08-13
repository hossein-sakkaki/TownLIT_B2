# apps/creative_editor/services/video_renderer.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-11.
# Last Update by Hossein Sakkaki on 2026-08-11.

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import math

from dataclasses import dataclass

from django.core.files.storage import default_storage
from PIL import Image

from apps.creative_editor.models import CreativeCompositionMedia
from apps.creative_editor.services.render_resources import resolve_render_resources
from apps.creative_editor.services.renderer import (
    CreativeCompositionRenderer,
    CreativeRenderContext,
    normalized_box,
)


class CreativeVideoRenderError(Exception):
    pass


@dataclass(frozen=True)
class CreativeVideoRenderResult:
    local_video_path: str
    poster: Image.Image
    width: int
    height: int
    duration_ms: int


@dataclass(frozen=True)
class _PreparedLayerInput:
    input_index: int
    layer: dict
    media: CreativeCompositionMedia | None
    source_path: str | None


class CreativeCompositionVideoRenderer:
    FRAME_RATE = 30

    VIDEO_CODEC = "libx264"
    VIDEO_PROFILE = "high"
    VIDEO_PIXEL_FORMAT = "yuv420p"

    AUDIO_CODEC = "aac"
    AUDIO_BITRATE = "192k"

    # Balanced production profile:
    # visually high quality without the render cost of medium/slow.
    CRF = 18
    PRESET = "fast"

    SCALE_FLAGS = "lanczos"

    def render(
        self,
        *,
        context: CreativeRenderContext,
        progress_callback,
    ) -> CreativeVideoRenderResult:
        document = context.document or {}
        canvas = document.get("canvas") or {}

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

        image_renderer = CreativeCompositionRenderer()
        image_renderer._validate_canvas_size(
            width=width,
            height=height,
        )

        visible_layers = [
            layer
            for layer in (document.get("layers") or [])
            if isinstance(layer, dict)
            and not layer.get("is_hidden", False)
        ]

        visible_layers.sort(
            key=lambda layer: (
                int(layer.get("z_index", 0)),
                str(layer.get("id", "")),
            )
        )

        video_layers = [
            layer
            for layer in visible_layers
            if layer.get("type") == "video"
        ]

        if not video_layers:
            raise CreativeVideoRenderError(
                "The document does not contain a video layer."
            )

        resources = resolve_render_resources(
            document=document,
            composition=context.composition,
        )

        duration_ms = self._resolve_output_duration_ms(
            video_layers=video_layers,
            resources=resources,
        )

        progress_callback(
            12,
            "preparing_video",
            "Preparing video render workspace",
        )

        workspace = tempfile.mkdtemp(
            prefix="townlit-creative-video-"
        )

        try:
            background_path = os.path.join(
                workspace,
                "background.png",
            )

            background = image_renderer._render_background(
                composition=context.composition,
                canvas=canvas,
                width=width,
                height=height,
            )

            background.save(
                background_path,
                format="PNG",
            )

            prepared_layers: list[_PreparedLayerInput] = []

            next_input_index = 1

            for layer_index, layer in enumerate(
                visible_layers
            ):
                layer_type = str(
                    layer.get("type") or ""
                )

                if layer_type == "video":
                    media = self._resolve_video_media(
                        layer=layer,
                        resources=resources,
                    )

                    source_path = self._materialize_media_video(
                        media=media,
                        workspace=workspace,
                    )

                    prepared_layers.append(
                        _PreparedLayerInput(
                            input_index=next_input_index,
                            layer=layer,
                            media=media,
                            source_path=source_path,
                        )
                    )

                    next_input_index += 1
                    continue

                if layer_type not in {
                    "image",
                    "text",
                    "sticker",
                }:
                    raise CreativeVideoRenderError(
                        f"Unsupported video render layer type: {layer_type!r}"
                    )

                overlay = self._render_static_layer(
                    renderer=image_renderer,
                    context=context,
                    layer=layer,
                    width=width,
                    height=height,
                    resources=resources,
                )

                overlay_path = os.path.join(
                    workspace,
                    f"layer-{layer_index}-{uuid.uuid4().hex}.png",
                )

                overlay.save(
                    overlay_path,
                    format="PNG",
                )

                prepared_layers.append(
                    _PreparedLayerInput(
                        input_index=next_input_index,
                        layer=layer,
                        media=None,
                        source_path=overlay_path,
                    )
                )

                next_input_index += 1

            progress_callback(
                28,
                "encoding_video",
                "Building FFmpeg composition",
            )

            output_path = os.path.join(
                workspace,
                "rendered.mp4",
            )

            self._run_ffmpeg(
                background_path=background_path,
                prepared_layers=prepared_layers,
                output_path=output_path,
                width=width,
                height=height,
                duration_ms=duration_ms,
            )

            progress_callback(
                86,
                "poster",
                "Generating video poster",
            )

            poster = self._extract_poster(
                video_path=output_path,
                workspace=workspace,
            )

            final_path = tempfile.mktemp(
                prefix="townlit-creative-render-",
                suffix=".mp4",
            )

            shutil.copy2(
                output_path,
                final_path,
            )

            return CreativeVideoRenderResult(
                local_video_path=final_path,
                poster=poster,
                width=width,
                height=height,
                duration_ms=duration_ms,
            )

        finally:
            shutil.rmtree(
                workspace,
                ignore_errors=True,
            )

    def _resolve_output_duration_ms(
        self,
        *,
        video_layers: list[dict],
        resources,
    ) -> int:
        durations: list[int] = []

        for layer in video_layers:
            media = self._resolve_video_media(
                layer=layer,
                resources=resources,
            )

            duration_ms = int(
                media.duration_ms or 0
            )

            if duration_ms <= 0:
                raise CreativeVideoRenderError(
                    f"Video media has no validated duration: {media.public_id}"
                )

            durations.append(
                duration_ms
            )

        return max(durations)

    def _resolve_video_media(
        self,
        *,
        layer: dict,
        resources,
    ) -> CreativeCompositionMedia:
        content = layer.get("content") or {}

        raw_media_id = str(
            content.get("media_id") or ""
        ).strip()

        try:
            media_id = str(
                uuid.UUID(raw_media_id)
            )
        except Exception as exc:
            raise CreativeVideoRenderError(
                f"Invalid video media identifier: {raw_media_id!r}"
            ) from exc

        media = resources.media.get(
            media_id
        )

        if media is None:
            raise CreativeVideoRenderError(
                f"Video media is unavailable: {media_id}"
            )

        if (
            media.media_type
            != CreativeCompositionMedia.MediaType.VIDEO
        ):
            raise CreativeVideoRenderError(
                f"Media {media_id} is not a video."
            )

        if not media.is_available():
            raise CreativeVideoRenderError(
                f"Video media is not ready: {media_id}"
            )

        return media

    def _materialize_media_video(
        self,
        *,
        media: CreativeCompositionMedia,
        workspace: str,
    ) -> str:
        if (
            media.source_mode
            != CreativeCompositionMedia.SourceMode.UPLOAD
        ):
            raise CreativeVideoRenderError(
                "Video content references are not supported by the renderer yet."
            )

        source = media.source_video

        source_key = str(
            getattr(source, "name", "") or ""
        ).lstrip("/")

        if not source_key:
            raise CreativeVideoRenderError(
                "Video source path is missing."
            )

        destination_root = os.path.join(
            workspace,
            f"video-{media.public_id}",
        )

        os.makedirs(
            destination_root,
            exist_ok=True,
        )

        if source_key.lower().endswith(
            ".m3u8"
        ):
            return self._materialize_hls_tree(
                source_key=source_key,
                destination_root=destination_root,
            )

        destination_path = os.path.join(
            destination_root,
            os.path.basename(source_key),
        )

        self._copy_storage_file(
            storage_key=source_key,
            destination_path=destination_path,
        )

        return destination_path

    def _materialize_hls_tree(
        self,
        *,
        source_key: str,
        destination_root: str,
    ) -> str:
        source_key = source_key.lstrip("/")

        source_root = os.path.dirname(
            source_key
        )

        visited: set[str] = set()

        def materialize(
            storage_key: str,
        ) -> str:
            storage_key = storage_key.lstrip("/")

            relative = os.path.relpath(
                storage_key,
                source_root,
            )

            if relative.startswith(".."):
                raise CreativeVideoRenderError(
                    "HLS playlist references a file outside its render root."
                )

            local_path = os.path.join(
                destination_root,
                relative,
            )

            if storage_key in visited:
                return local_path

            visited.add(
                storage_key
            )

            os.makedirs(
                os.path.dirname(local_path),
                exist_ok=True,
            )

            if storage_key.lower().endswith(
                ".m3u8"
            ):
                with default_storage.open(
                    storage_key,
                    "rb",
                ) as source:
                    content = (
                        source.read()
                        .decode(
                            "utf-8",
                            errors="strict",
                        )
                    )

                rewritten_lines: list[str] = []

                for line in content.splitlines():
                    stripped = line.strip()

                    if (
                        stripped
                        and not stripped.startswith("#")
                    ):
                        child_key = os.path.normpath(
                            os.path.join(
                                os.path.dirname(storage_key),
                                stripped,
                            )
                        ).replace("\\", "/")

                        materialize(
                            child_key
                        )

                    for uri in re.findall(
                        r'URI="([^"]+)"',
                        line,
                    ):
                        child_key = os.path.normpath(
                            os.path.join(
                                os.path.dirname(storage_key),
                                uri,
                            )
                        ).replace("\\", "/")

                        materialize(
                            child_key
                        )

                    rewritten_lines.append(
                        line
                    )

                with open(
                    local_path,
                    "w",
                    encoding="utf-8",
                ) as destination:
                    destination.write(
                        "\n".join(
                            rewritten_lines
                        )
                    )

                return local_path

            self._copy_storage_file(
                storage_key=storage_key,
                destination_path=local_path,
            )

            return local_path

        return materialize(
            source_key
        )

    def _copy_storage_file(
        self,
        *,
        storage_key: str,
        destination_path: str,
    ) -> None:
        if not default_storage.exists(
            storage_key
        ):
            raise CreativeVideoRenderError(
                f"Render source is missing from storage: {storage_key}"
            )

        os.makedirs(
            os.path.dirname(destination_path),
            exist_ok=True,
        )

        with default_storage.open(
            storage_key,
            "rb",
        ) as source:
            with open(
                destination_path,
                "wb",
            ) as destination:
                shutil.copyfileobj(
                    source,
                    destination,
                )

    def _render_static_layer(
        self,
        *,
        renderer: CreativeCompositionRenderer,
        context: CreativeRenderContext,
        layer: dict,
        width: int,
        height: int,
        resources,
    ) -> Image.Image:
        output = Image.new(
            "RGBA",
            (width, height),
            (0, 0, 0, 0),
        )

        layer_type = str(
            layer.get("type") or ""
        )

        if layer_type == "text":
            renderer._render_text_layer(
                output=output,
                layer=layer,
            )

        elif layer_type == "sticker":
            renderer._render_sticker_layer(
                output=output,
                layer=layer,
                resources=resources,
            )

        elif layer_type == "image":
            renderer._render_image_layer(
                output=output,
                layer=layer,
                resources=resources,
            )

        else:
            raise CreativeVideoRenderError(
                f"Unsupported static video layer: {layer_type!r}"
            )

        return output

    def _run_ffmpeg(
        self,
        *,
        background_path: str,
        prepared_layers: list[_PreparedLayerInput],
        output_path: str,
        width: int,
        height: int,
        duration_ms: int,
    ) -> None:
        duration_seconds = max(
            duration_ms / 1000.0,
            0.001,
        )

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(self.FRAME_RATE),
            "-i",
            background_path,
        ]

        for prepared in prepared_layers:
            if not prepared.source_path:
                raise CreativeVideoRenderError(
                    "Prepared render layer has no source path."
                )

            if prepared.media is None:
                command.extend([
                    "-loop",
                    "1",
                    "-framerate",
                    str(self.FRAME_RATE),
                    "-i",
                    prepared.source_path,
                ])
            else:
                command.extend([
                    "-i",
                    prepared.source_path,
                ])

        filters: list[str] = [
            (
                f"[0:v]"
                f"scale={width}:{height}:flags={self.SCALE_FLAGS},"
                f"setsar=1,"
                f"format=rgba"
                f"[base0]"
            )
        ]

        current_base = "base0"
        audio_inputs: list[str] = []

        for index, prepared in enumerate(
            prepared_layers
        ):
            next_base = f"base{index + 1}"

            if prepared.media is None:
                overlay_label = f"static{index}"

                filters.append(
                    f"[{prepared.input_index}:v]"
                    f"scale={width}:{height}:flags={self.SCALE_FLAGS},"
                    f"setsar=1,"
                    f"format=rgba"
                    f"[{overlay_label}]"
                )

                filters.append(
                    f"[{current_base}]"
                    f"[{overlay_label}]"
                    f"overlay="
                    f"x=0:"
                    f"y=0:"
                    f"format=auto:"
                    f"eof_action=pass"
                    f"[{next_base}]"
                )

            else:
                video_label = f"video{index}"

                (
                    video_filter,
                    overlay_x,
                    overlay_y,
                ) = self._build_video_layer_filter(
                    input_index=prepared.input_index,
                    layer=prepared.layer,
                    canvas_width=width,
                    canvas_height=height,
                    label=video_label,
                    duration_seconds=duration_seconds,
                )

                filters.append(
                    video_filter
                )

                filters.append(
                    f"[{current_base}]"
                    f"[{video_label}]"
                    f"overlay="
                    f"x={overlay_x}:"
                    f"y={overlay_y}:"
                    f"format=auto:"
                    f"eof_action=pass"
                    f"[{next_base}]"
                )

                if self._has_audio_stream(
                    prepared.source_path
                ):
                    audio_inputs.append(
                        f"[{prepared.input_index}:a]"
                    )

            current_base = next_base

        filters.append(
            f"[{current_base}]"
            f"setsar=1,"
            f"format=yuv420p"
            f"[video_out]"
        )

        if audio_inputs:
            if len(audio_inputs) == 1:
                filters.append(
                    f"{audio_inputs[0]}"
                    f"atrim=0:{duration_seconds:.3f},"
                    f"asetpts=PTS-STARTPTS"
                    f"[audio_out]"
                )

            else:
                prepared_audio_labels: list[str] = []

                for index, audio_input in enumerate(
                    audio_inputs
                ):
                    audio_label = f"audio{index}"

                    filters.append(
                        f"{audio_input}"
                        f"atrim=0:{duration_seconds:.3f},"
                        f"asetpts=PTS-STARTPTS"
                        f"[{audio_label}]"
                    )

                    prepared_audio_labels.append(
                        f"[{audio_label}]"
                    )

                filters.append(
                    "".join(
                        prepared_audio_labels
                    )
                    + "amix="
                    + f"inputs={len(prepared_audio_labels)}:"
                    + "duration=longest:"
                    + "normalize=0"
                    + "[audio_out]"
                )

        filter_complex = ";".join(
            filters
        )

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[video_out]",
        ])

        if audio_inputs:
            command.extend([
                "-map",
                "[audio_out]",
                "-c:a",
                self.AUDIO_CODEC,
                "-b:a",
                self.AUDIO_BITRATE,
            ])
        else:
            command.append(
                "-an"
            )

        command.extend([
            "-t",
            f"{duration_seconds:.3f}",
            "-r",
            str(self.FRAME_RATE),

            "-c:v",
            self.VIDEO_CODEC,

            "-preset",
            self.PRESET,

            "-crf",
            str(self.CRF),

            "-profile:v",
            self.VIDEO_PROFILE,

            "-pix_fmt",
            self.VIDEO_PIXEL_FORMAT,

            "-movflags",
            "+faststart",

            output_path,
        ])

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error = (
                result.stderr
                or result.stdout
                or "Unknown FFmpeg error."
            ).strip()

            raise CreativeVideoRenderError(
                "FFmpeg creative render failed: "
                + error[-12_000:]
            )

        if (
            not os.path.exists(output_path)
            or os.path.getsize(output_path) <= 0
        ):
            raise CreativeVideoRenderError(
                "FFmpeg completed without producing "
                "a valid video output."
            )

    def _build_video_layer_filter(
        self,
        *,
        input_index: int,
        layer: dict,
        canvas_width: int,
        canvas_height: int,
        label: str,
        duration_seconds: float,
    ) -> tuple[str, str, str]:
        """
        Build a rigid rectangular video transform.

        The video is first resolved into its unrotated layer box.
        Rotation is then applied without any post-rotation scaling.
        The transparent rotated bounding box is calculated explicitly
        so the four 90-degree corners are never clipped or deformed.
        """

        transform = layer.get("transform") or {}
        content = layer.get("content") or {}

        _, _, target_width, target_height = normalized_box(
            transform=transform,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )

        target_width = max(int(target_width), 1)
        target_height = max(int(target_height), 1)

        center_x = canvas_width * float(transform.get("center_x", 0.5))
        center_y = canvas_height * float(transform.get("center_y", 0.5))

        rotation_radians = float(transform.get("rotation", 0) or 0)

        chain: list[str] = [
            "setpts=PTS-STARTPTS",
            "setsar=1",
        ]

        crop = content.get("crop")

        if isinstance(crop, dict):
            crop_x = max(0.0, min(1.0, float(crop.get("x", 0))))
            crop_y = max(0.0, min(1.0, float(crop.get("y", 0))))

            crop_width = max(
                0.0001,
                min(1.0 - crop_x, float(crop.get("width", 1))),
            )

            crop_height = max(
                0.0001,
                min(1.0 - crop_y, float(crop.get("height", 1))),
            )

            chain.append(
                "crop="
                f"iw*{crop_width:.8f}:"
                f"ih*{crop_height:.8f}:"
                f"iw*{crop_x:.8f}:"
                f"ih*{crop_y:.8f}"
            )

            chain.append("setsar=1")

        content_mode = str(
            content.get("content_mode", "fill") or "fill"
        ).strip().lower()

        if content_mode == "fill":
            chain.append(
                f"scale={target_width}:{target_height}:"
                "force_original_aspect_ratio=increase:"
                f"flags={self.SCALE_FLAGS}"
            )

            chain.append("setsar=1")

            chain.append(
                f"crop={target_width}:{target_height}:"
                "(iw-ow)/2:(ih-oh)/2"
            )

        elif content_mode == "fit":
            chain.append(
                f"scale={target_width}:{target_height}:"
                "force_original_aspect_ratio=decrease:"
                f"flags={self.SCALE_FLAGS}"
            )

            chain.append("setsar=1")
            chain.append("format=rgba")

            chain.append(
                f"pad={target_width}:{target_height}:"
                "(ow-iw)/2:(oh-ih)/2:"
                "color=black@0"
            )

        else:
            raise CreativeVideoRenderError(
                f"Unsupported video content mode: {content_mode!r}"
            )

        chain.extend([
            "setsar=1",
            "format=rgba",
        ])

        if transform.get("flip_x", False):
            chain.append("hflip")

        if transform.get("flip_y", False):
            chain.append("vflip")

        if abs(rotation_radians) > 0.00001:
            cosine = abs(math.cos(rotation_radians))
            sine = abs(math.sin(rotation_radians))

            rotated_width = int(
                math.ceil(
                    target_width * cosine
                    + target_height * sine
                )
            )

            rotated_height = int(
                math.ceil(
                    target_width * sine
                    + target_height * cosine
                )
            )

            
            # The layer remains rectangular. These dimensions
            # describe only the transparent axis-aligned box
            # surrounding that rotated rectangle.
            rotated_width = max(rotated_width, 1)
            rotated_height = max(rotated_height, 1)

            chain.append(
                "rotate="
                f"{rotation_radians:.12f}:"
                f"ow={rotated_width}:"
                f"oh={rotated_height}:"
                "c=black@0:"
                "bilinear=1"
            )

            chain.append("setsar=1")

        opacity = max(
            0.0,
            min(
                1.0,
                float(layer.get("opacity", 1) or 0),
            ),
        )

        if opacity < 0.9999:
            chain.append(
                f"colorchannelmixer=aa={opacity:.8f}"
            )

        chain.append(
            "tpad="
            "stop_mode=clone:"
            f"stop_duration={duration_seconds:.3f}"
        )

        filter_expression = (
            f"[{input_index}:v]"
            + ",".join(chain)
            + f"[{label}]"
        )

        # Rotation expands only the transparent bounding box.
        # Its center must remain exactly at the Creative layer center.
        overlay_x = f"{center_x:.6f}-overlay_w/2"
        overlay_y = f"{center_y:.6f}-overlay_h/2"

        return filter_expression, overlay_x, overlay_y


    def _has_audio_stream(
        self,
        path: str,
    ) -> bool:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return False

        try:
            payload = json.loads(
                result.stdout or "{}"
            )
        except Exception:
            return False

        return bool(
            payload.get(
                "streams"
            )
        )

    def _extract_poster(
        self,
        *,
        video_path: str,
        workspace: str,
    ) -> Image.Image:
        poster_path = os.path.join(
            workspace,
            "poster.jpg",
        )

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "0.10",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            poster_path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise CreativeVideoRenderError(
                "Video poster generation failed: "
                + (result.stderr or "").strip()[-4000:]
            )

        with Image.open(
            poster_path
        ) as image:
            return image.convert(
                "RGB"
            ).copy()