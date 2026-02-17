# apps/subtitles/services/voice_tone.py

from __future__ import annotations
from typing import Any, Dict, List


def _count_words(text: str) -> int:
    return len([w for w in (text or "").strip().split() if w])


def build_tone_profile_from_stt(stt: dict) -> Dict[str, Any]:
    """
    Build a SAFE tone profile from STT segments.
    - No voice cloning
    - Only pacing/pauses hints for text shaping
    """

    segs: List[dict] = stt.get("segments", []) or []
    if not segs:
        return {
            "pace": "normal",
            "pause_style": "normal",
            "energy": "warm",
            "target_wps": 2.6,  # words per second
        }

    start = float(segs[0].get("start", 0.0))
    end = float(segs[-1].get("end", start))
    total_sec = max(0.1, end - start)

    total_words = 0
    for s in segs:
        total_words += _count_words(s.get("text", ""))

    wps = float(total_words) / total_sec

    # Pace buckets (simple + stable)
    if wps < 2.1:
        pace, energy, target_wps = "slow", "calm", 2.0
    elif wps > 3.2:
        pace, energy, target_wps = "fast", "energetic", 3.1
    else:
        pace, energy, target_wps = "normal", "warm", 2.6

    # Pause style based on gaps
    gaps = []
    prev_end = None
    for s in segs:
        s_start = float(s.get("start", 0.0))
        if prev_end is not None:
            gaps.append(max(0.0, s_start - prev_end))
        prev_end = float(s.get("end", s_start))

    avg_gap = (sum(gaps) / len(gaps)) if gaps else 0.0
    if avg_gap > 0.65:
        pause_style = "pausey"
    elif avg_gap < 0.25:
        pause_style = "tight"
    else:
        pause_style = "normal"

    return {
        "pace": pace,
        "pause_style": pause_style,
        "energy": energy,
        "target_wps": round(target_wps, 2),
        "measured_wps": round(wps, 2),
        "avg_gap_s": round(avg_gap, 2),
    }
