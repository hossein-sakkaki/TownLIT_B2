# apps/media_conversion/services/hls_preview_source.py
# TownLIT Backend
#
# Created by Hossein Sakkaki on 2026-11-02.
# Last Update by Hossein Sakkaki on 2026-11-02.

"""Stage a small, unencrypted HLS excerpt for the existing preview encoder."""

from __future__ import annotations

import math
import os
import posixpath
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


MAX_PLAYLIST_BYTES = 512 * 1024
MAX_SEGMENT_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_SEGMENTS = 16


class HLSPreviewSourceError(ValueError):
    pass


@dataclass(frozen=True)
class HLSSegment:
    key: str
    duration: float


def safe_storage_key(raw: object) -> str:
    """Reject absolute, URL, traversal, and query-bearing storage keys."""
    if not isinstance(raw, str):
        raise HLSPreviewSourceError("Storage key is not a string")

    value = raw.strip()
    if not value or value.startswith(("/", "\\")):
        raise HLSPreviewSourceError("Storage key must be relative")
    if "\\" in value or "?" in value or "#" in value:
        raise HLSPreviewSourceError("Invalid storage key")
    if urlsplit(value).scheme or urlsplit(value).netloc:
        raise HLSPreviewSourceError("Remote URLs are not supported")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise HLSPreviewSourceError("Invalid storage key components")
    return value


def _resolve_reference(base_playlist_key: str, uri: str, root: str) -> str:
    relative = safe_storage_key(uri)
    resolved = posixpath.normpath(
        posixpath.join(posixpath.dirname(base_playlist_key), relative)
    )
    if posixpath.commonpath((root, resolved)) != root:
        raise HLSPreviewSourceError("HLS reference escapes video directory")
    return resolved


def _read_small_storage_object(storage, key: str, max_bytes: int) -> bytes:
    with storage.open(key, "rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HLSPreviewSourceError("HLS object exceeds inspection limit")
    return data


def select_hls_segments(
    *,
    storage,
    master_key: str,
    quality_playlist_key: str,
    seconds: float = 3.5,
) -> list[HLSSegment]:
    """Select the first complete MPEG-TS segments covering preview duration."""
    master = safe_storage_key(master_key)
    playlist = safe_storage_key(quality_playlist_key)
    root = posixpath.dirname(master)

    if not root or posixpath.commonpath((root, playlist)) != root:
        raise HLSPreviewSourceError("Playlist is outside video directory")
    if not master.endswith(".m3u8") or not playlist.endswith(".m3u8"):
        raise HLSPreviewSourceError("Expected HLS playlist keys")
    if not math.isfinite(seconds) or seconds <= 0:
        raise HLSPreviewSourceError("Invalid preview duration")

    raw = _read_small_storage_object(storage, playlist, MAX_PLAYLIST_BYTES)
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise HLSPreviewSourceError("Non-UTF-8 HLS playlist") from exc

    if not lines or lines[0].strip() != "#EXTM3U":
        raise HLSPreviewSourceError("Not an HLS playlist")

    disallowed_tags = (
        "#EXT-X-KEY:",
        "#EXT-X-SESSION-KEY:",
        "#EXT-X-MAP:",
        "#EXT-X-BYTERANGE:",
        "#EXT-X-DISCONTINUITY",
    )
    if any(line.strip().startswith(disallowed_tags) for line in lines):
        raise HLSPreviewSourceError("Unsupported encrypted or fragmented HLS")

    selected: list[HLSSegment] = []
    pending_duration: float | None = None
    covered = 0.0

    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            try:
                pending_duration = float(line[8:].split(",", 1)[0])
            except (ValueError, OverflowError) as exc:
                raise HLSPreviewSourceError("Invalid segment duration") from exc
            if not math.isfinite(pending_duration) or pending_duration <= 0:
                raise HLSPreviewSourceError("Invalid segment duration")
            continue
        if line.startswith("#"):
            continue
        if pending_duration is None:
            raise HLSPreviewSourceError("HLS segment without EXTINF")
        if not urlsplit(line).path.lower().endswith(".ts"):
            raise HLSPreviewSourceError("Only MPEG-TS segments are supported")
        if len(selected) >= MAX_SEGMENTS:
            raise HLSPreviewSourceError("Too many segments required")
        key = _resolve_reference(playlist, line, root)
        selected.append(HLSSegment(key=key, duration=pending_duration))
        covered += pending_duration
        pending_duration = None
        if covered >= seconds:
            break

    if covered < seconds or not selected:
        raise HLSPreviewSourceError("Insufficient HLS segment duration")
    return selected


def stage_hls_preview_source(
    *,
    storage,
    segments: list[HLSSegment],
    directory: str | os.PathLike[str],
) -> str:
    """Copy selected segments and write a minimal local HLS playlist."""
    if not segments or len(segments) > MAX_SEGMENTS:
        raise HLSPreviewSourceError("Invalid segment list")

    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    playlist_lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{math.ceil(max(s.duration for s in segments))}",
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]

    total_bytes = 0
    for index, segment in enumerate(segments):
        name = f"segment_{index:03d}.ts"
        local_path = destination / name
        size = 0
        with storage.open(segment.key, "rb") as source, local_path.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                total_bytes += len(chunk)
                if size > MAX_SEGMENT_BYTES or total_bytes > MAX_TOTAL_BYTES:
                    raise HLSPreviewSourceError("HLS segment download limit exceeded")
                output.write(chunk)
        if size == 0:
            raise HLSPreviewSourceError("Empty HLS segment")
        playlist_lines.extend((f"#EXTINF:{segment.duration:.6f},", name))

    playlist_lines.append("#EXT-X-ENDLIST")
    playlist_path = destination / "preview_source.m3u8"
    playlist_path.write_text("\n".join(playlist_lines) + "\n", encoding="utf-8")
    return str(playlist_path)
