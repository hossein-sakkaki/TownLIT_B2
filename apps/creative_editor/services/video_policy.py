#
#  apps/creative_editor/services/video_policy.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-11.
#  Last Update by Hossein Sakkaki on 2026-08-11.
#

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class CreativeVideoPolicy:
    minimum_duration_ms: int
    maximum_duration_ms: int
    duration_tolerance_ms: int


@dataclass(frozen=True)
class CreativeVideoInspection:
    duration_ms: int


def get_creative_video_policy() -> CreativeVideoPolicy:
    minimum_seconds = max(
        1.0,
        float(
            getattr(
                settings,
                "CREATIVE_VIDEO_MIN_DURATION_SECONDS",
                15,
            )
        ),
    )

    maximum_seconds = max(
        minimum_seconds,
        float(
            getattr(
                settings,
                "CREATIVE_VIDEO_MAX_DURATION_SECONDS",
                60,
            )
        ),
    )

    tolerance_ms = max(
        0,
        int(
            getattr(
                settings,
                "CREATIVE_VIDEO_DURATION_TOLERANCE_MS",
                250,
            )
        ),
    )

    return CreativeVideoPolicy(
        minimum_duration_ms=int(round(minimum_seconds * 1000)),
        maximum_duration_ms=int(round(maximum_seconds * 1000)),
        duration_tolerance_ms=tolerance_ms,
    )


def inspect_uploaded_creative_video(
    uploaded_file,
) -> CreativeVideoInspection:
    """
    Probe one uploaded video before conversion is queued.
    """

    path = None
    temporary_path = False

    original_position = None

    try:
        try:
            original_position = uploaded_file.tell()
        except Exception:
            original_position = None

        temporary_file_path = getattr(
            uploaded_file,
            "temporary_file_path",
            None,
        )

        if callable(temporary_file_path):
            path = temporary_file_path()
        else:
            suffix = os.path.splitext(
                str(
                    getattr(
                        uploaded_file,
                        "name",
                        "",
                    )
                    or ""
                )
            )[1]

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as output:
                path = output.name
                temporary_path = True

                try:
                    uploaded_file.seek(0)
                except Exception:
                    pass

                chunks = getattr(
                    uploaded_file,
                    "chunks",
                    None,
                )

                if callable(chunks):
                    for chunk in chunks():
                        output.write(chunk)
                else:
                    output.write(
                        uploaded_file.read()
                    )

        timeout = max(
            3,
            int(
                getattr(
                    settings,
                    "CREATIVE_VIDEO_PROBE_TIMEOUT_SECONDS",
                    15,
                )
            ),
        )

        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type:format=duration",
            "-of",
            "json",
            path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=timeout,
        )

        payload = json.loads(
            result.stdout.decode(
                "utf-8",
                "ignore",
            )
        )

        streams = payload.get("streams") or []

        if not streams:
            raise ValidationError(
                {
                    "source_video": (
                        "The uploaded file does not contain "
                        "a readable video stream."
                    ),
                }
            )

        duration_value = (
            payload.get("format") or {}
        ).get("duration")

        try:
            duration_seconds = float(
                duration_value
            )
        except (
            TypeError,
            ValueError,
        ):
            duration_seconds = 0

        if duration_seconds <= 0:
            raise ValidationError(
                {
                    "source_video": (
                        "The uploaded video duration "
                        "could not be determined."
                    ),
                }
            )

        return CreativeVideoInspection(
            duration_ms=max(
                1,
                int(
                    round(
                        duration_seconds
                        * 1000
                    )
                ),
            )
        )

    except ValidationError:
        raise

    except (
        subprocess.SubprocessError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise ValidationError(
            {
                "source_video": (
                    "The uploaded video could not "
                    "be inspected."
                ),
            }
        ) from exc

    finally:
        if original_position is not None:
            try:
                uploaded_file.seek(
                    original_position
                )
            except Exception:
                pass

        if temporary_path and path:
            try:
                os.remove(path)
            except OSError:
                pass


def validate_creative_video_duration(
    duration_ms: int,
) -> None:
    policy = get_creative_video_policy()

    minimum = (
        policy.minimum_duration_ms
        - policy.duration_tolerance_ms
    )

    maximum = (
        policy.maximum_duration_ms
        + policy.duration_tolerance_ms
    )

    if duration_ms < minimum:
        raise ValidationError(
            {
                "source_video": (
                    "The selected video is shorter than "
                    "the current Creative Editor limit."
                ),
            }
        )

    if duration_ms > maximum:
        raise ValidationError(
            {
                "source_video": (
                    "The selected video is longer than "
                    "the current Creative Editor limit."
                ),
            }
        )