# apps/subtitles/services/subtitle_renderers.py

from __future__ import annotations


def _ms_to_vtt(ts_ms: int) -> str:
    # VTT uses '.' for ms
    h = ts_ms // 3600000
    m = (ts_ms % 3600000) // 60000
    s = (ts_ms % 60000) // 1000
    ms = ts_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _ms_to_srt(ts_ms: int) -> str:
    # SRT uses ',' for ms
    h = ts_ms // 3600000
    m = (ts_ms % 3600000) // 60000
    s = (ts_ms % 60000) // 1000
    ms = ts_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_vtt(rows: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for r in rows:
        start = _ms_to_vtt(int(r["start_ms"]))
        end = _ms_to_vtt(int(r["end_ms"]))
        text = (r["text"] or "").strip()
        if not text:
            continue
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_srt(rows: list[dict]) -> str:
    lines = []
    i = 1
    for r in rows:
        text = (r["text"] or "").strip()
        if not text:
            continue
        start = _ms_to_srt(int(r["start_ms"]))
        end = _ms_to_srt(int(r["end_ms"]))
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
        i += 1
    return "\n".join(lines).strip() + "\n"
