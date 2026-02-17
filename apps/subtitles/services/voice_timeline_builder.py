# apps/subtitles/services/voice_timeline_builder.py

from __future__ import annotations

import os
import re
import json
import shutil
import tempfile
import subprocess
import inspect
import hashlib
from enum import Enum
from django.core.cache import cache
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

from django.core.files.storage import default_storage

from apps.subtitles.services.tts_openai import synthesize_speech_to_local_mp3
from apps.subtitles.services.voice_humanizer import humanize_for_voice


# ----------------------------------------------
# Enums
# ----------------------------------------------
class VoiceFailReason(str, Enum):
    ZERO_DURATION = "zero_duration"
    TOO_SHORT = "too_short"
    OVER_SLOT_TRIMMABLE = "over_slot_trimmable"
    OVER_SLOT_TOO_LARGE = "over_slot_too_large"
    ACCEPTABLE = "acceptable"



# ----------------------------------------------
# Cue model
# ----------------------------------------------
@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str


# ----------------------------------------------
# Cache
# ----------------------------------------------
VOICE_CUE_CACHE_TTL = 60 * 60 * 24 * 60  # 60 days

def _cue_cache_key(
    *,
    text: str,
    language: str,
    voice_id: str,
    gender: str | None,
    slot_ms: int,
) -> str:
    raw = f"{language}|{voice_id}|{gender or ''}|{slot_ms}|{text}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"voice_cue:{h}"


# ----------------------------------------------
# Utils
# ----------------------------------------------
_TIME_RE = re.compile(r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d{3})")

def _to_ms(ts: str) -> int:
    m = _TIME_RE.search(ts.strip())
    if not m:
        raise ValueError(f"Bad timestamp: {ts}")
    h = int(m.group("h"))
    mi = int(m.group("m"))
    s = int(m.group("s"))
    ms = int(m.group("ms"))
    return ((h * 3600 + mi * 60 + s) * 1000) + ms


def parse_vtt_to_cues(vtt_text: str) -> List[Cue]:
    """Parse VTT into ordered cues."""
    if not vtt_text:
        return []

    lines = [ln.rstrip("\n") for ln in vtt_text.splitlines()]
    cues: List[Cue] = []

    i = 0
    while i < len(lines):
        ln = lines[i].strip()

        if not ln or ln.startswith("WEBVTT"):
            i += 1
            continue

        if ln.isdigit():
            i += 1
            continue

        if "-->" in ln:
            parts = [p.strip() for p in ln.split("-->")]
            start = parts[0]
            end = parts[1].split(" ")[0].strip()

            start_ms = _to_ms(start)
            end_ms = _to_ms(end)

            i += 1
            text_lines: List[str] = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1

            text = " ".join(text_lines).strip()
            if text and end_ms > start_ms:
                cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text=text))

            i += 1
            continue

        i += 1

    cues.sort(key=lambda c: c.start_ms)
    return cues


# ----------------------------------------------
# Quality classification
# ----------------------------------------------
def _classify_voice_result(
    *,
    real_ms: int,
    slot_ms: int,
    overrun_tolerance: float,
) -> VoiceFailReason:
    """
    Classify TTS output quality relative to slot.
    This drives retry decisions (Stage 4).
    """

    if real_ms <= 0:
        return VoiceFailReason.ZERO_DURATION

    if real_ms < int(slot_ms * 0.45):
        return VoiceFailReason.TOO_SHORT

    if real_ms <= int(slot_ms * overrun_tolerance):
        return VoiceFailReason.ACCEPTABLE

    if real_ms <= int(slot_ms * 1.25):
        return VoiceFailReason.OVER_SLOT_TRIMMABLE

    return VoiceFailReason.OVER_SLOT_TOO_LARGE


# ----------------------------------------------
# Retry policy
# ----------------------------------------------
def _should_retry_voice(
    *,
    reason: VoiceFailReason,
    attempt: int,
) -> bool:
    """
    Smart retry policy.
    Retry ONLY when TTS might improve.
    """

    if attempt >= 1:
        return False

    # Only retry for genuine TTS failures
    return reason in {
        VoiceFailReason.ZERO_DURATION,
    }


# ----------------------------------------------
# wav trimming
# ----------------------------------------------
def _trim_wav_to_ms(in_wav: str, out_wav: str, dur_ms: int) -> None:
    """
    Hard clamp to dur_ms (ms) with a tiny fade out to avoid clicks.
    """
    sec = max(dur_ms, 0) / 1000.0
    fade = min(0.06, max(0.02, sec * 0.03))  # 20-60ms
    # atrim is sample-accurate enough; afade prevents harsh cut
    _run([
        "ffmpeg",
        "-y",
        "-i", in_wav,
        "-filter:a", f"atrim=0:{sec:.6f},afade=t=out:st={max(0.0, sec-fade):.6f}:d={fade:.6f}",
        "-ar", "24000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        out_wav,
    ])


# ----------------------------------------------
# ffmpeg helpers
# ----------------------------------------------
def _run(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _probe_duration_ms(path: str) -> int:
    """ffprobe duration (ms)."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    out = subprocess.check_output(cmd)
    data = json.loads(out.decode("utf-8"))
    dur = float(data.get("format", {}).get("duration") or 0.0)
    return int(dur * 1000)


def _make_silence_wav(out_path: str, dur_ms: int) -> None:
    """Generate silence wav of dur_ms."""
    sec = max(dur_ms, 0) / 1000.0
    _run([
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{sec:.3f}",
        "-acodec", "pcm_s16le",
        out_path,
    ])


def _mp3_to_wav(in_mp3: str, out_wav: str) -> None:
    _run([
        "ffmpeg",
        "-y",
        "-i", in_mp3,
        "-ar", "24000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        out_wav,
    ])


def _speedup_wav(in_wav: str, out_wav: str, speed: float) -> None:
    """
    Speed up audio slightly to fit a slot.
    - speed > 1 => faster (shorter)
    - We NEVER slow down here (slowdown sounds unnatural)
    """
    speed = max(1.0, float(speed))

    # atempo supports 0.5..2.0; chain if needed
    filters: List[float] = []
    x = speed
    while x > 2.0:
        filters.append(2.0)
        x /= 2.0
    filters.append(x)

    chain = ",".join([f"atempo={f:.6f}" for f in filters])

    _run([
        "ffmpeg",
        "-y",
        "-i", in_wav,
        "-filter:a", chain,
        "-ar", "24000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        out_wav,
    ])


def _concat_wavs(wavs: List[str], out_wav: str) -> None:
    """Concat wavs losslessly via concat demuxer."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        for p in wavs:
            f.write(f"file '{p}'\n".encode("utf-8"))
        list_path = f.name

    try:
        _run([
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            out_wav,
        ])
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass


def _wav_to_mp3(in_wav: str, out_mp3: str) -> None:
    _run([
        "ffmpeg",
        "-y",
        "-i", in_wav,
        "-c:a", "libmp3lame",
        "-q:a", "4",
        out_mp3,
    ])


# ----------------------------------------------
# Slot-aware helpers (pace + tone)
# ----------------------------------------------
def _chars_per_sec(language: str) -> float:
    """Rough speaking density (chars/sec)."""
    lang = (language or "").strip().lower()
    if lang.startswith("en"):
        return 13.0
    if lang.startswith("ar"):
        return 10.8
    if lang.startswith(("fa", "ur")):
        return 11.6
    return 12.5


def _tone_pace_multiplier(tone_profile: Optional[Dict[str, Any]]) -> float:
    """
    Pace multiplier derived from tone_profile.
    - If pace is slower -> fewer chars per slot
    - If faster -> slightly more chars per slot
    """
    if not tone_profile:
        return 1.0

    pace = (tone_profile.get("pace") or "").strip().lower()
    # Expected values: "slow" | "normal" | "fast" (you control this)
    if pace == "slow":
        return 0.90
    if pace == "fast":
        return 1.06
    return 1.0


def _slot_max_chars(language: str, slot_ms: int, tone_profile: Optional[Dict[str, Any]]) -> int:
    """
    Compute max_chars to keep spoken text inside slot naturally.
    Important: lower max => less need for speed hacks.
    """
    sec = max(slot_ms, 220) / 1000.0
    cps = _chars_per_sec(language)
    pace_mul = _tone_pace_multiplier(tone_profile)

    # Small headroom; too big causes overruns
    base = sec * cps * 1.10 * pace_mul
    return max(16, int(base))


def _humanize_slot_text(
    *,
    text: str,
    language: str,
    max_chars: int,
    tone_profile: Optional[Dict[str, Any]],
) -> str:
    """
    Humanize for speech + enforce slot limit.
    This is the main lever to avoid "fast/slow" audio.
    """
    src = (text or "").strip()
    if not src:
        return src

    # Detect if humanizer supports tone_profile (no breaking change)
    sig = inspect.signature(humanize_for_voice)
    supports_tone = "tone_profile" in sig.parameters

    if supports_tone:
        out = humanize_for_voice(text=src, language=language, max_chars=max_chars, tone_profile=tone_profile)
    else:
        out = humanize_for_voice(text=src, language=language, max_chars=max_chars)

    out = (out or "").strip()
    return out if out else src


# ----------------------------------------------
# Main builder
# ----------------------------------------------
# apps/subtitles/services/voice_timeline_builder.py

def build_voice_audio_from_vtt_timeline(
    *,
    vtt_text: str,
    target_language: str,
    voice_id: str,
    gender: str | None = None,
    tone_profile: Optional[Dict[str, Any]] = None,
) -> Tuple[str, int]:
    """
    Timeline-based voice synthesis (cost-balanced).

    Cost policy (Stage 3):
    - Cue-level cache (no re-TTS for healthy segments)
    - Max 1 retry per cue
    - Prefer trim / tiny speed-up over re-TTS
    """

    cues = parse_vtt_to_cues(vtt_text)
    if not cues:
        raise RuntimeError("No VTT cues found")

    tmpdir = tempfile.mkdtemp(prefix="tl_voice_")
    wav_parts: List[str] = []

    # -----------------------------
    # Safe knobs (Stage 1 + 3)
    # -----------------------------
    MIN_SLOT_MS = 180
    MAX_SPEEDUP = 1.08           # <= 8%
    OVERRUN_TOLERANCE = 1.05     
    MAX_RETRY = 1                # hard cap (cost saver)

    cursor_ms = 0

    try:
        for idx, cue in enumerate(cues):
            slot_ms = max(0, cue.end_ms - cue.start_ms)
            if slot_ms < MIN_SLOT_MS:
                continue

            # 0) Insert silence gap if needed
            gap_ms = max(0, cue.start_ms - cursor_ms)
            if gap_ms > 0:
                gap_wav = os.path.join(tmpdir, f"gap_{idx:05d}.wav")
                _make_silence_wav(gap_wav, gap_ms)
                wav_parts.append(gap_wav)
                cursor_ms += gap_ms

            # 1) Slot-aware max chars
            base_max_chars = _slot_max_chars(
                target_language,
                slot_ms,
                tone_profile,
            )

            best_wav: Optional[str] = None
            best_ms: Optional[int] = None

            # 2) At most 1 retry
            for attempt in range(MAX_RETRY + 1):
                max_chars = max(10, int(base_max_chars * (0.90 ** attempt)))

                spoken = _humanize_slot_text(
                    text=cue.text,
                    language=target_language,
                    max_chars=max_chars,
                    tone_profile=tone_profile,
                )

                # ----------------------------------
                # Cue-level cache (Stage 3 핵심)
                # ----------------------------------
                cache_key = _cue_cache_key(
                    text=spoken,
                    language=target_language,
                    voice_id=voice_id,
                    gender=gender,
                    slot_ms=slot_ms,
                )

                cached_wav = cache.get(cache_key)
                if cached_wav and os.path.exists(cached_wav):
                    seg_wav = cached_wav
                    real_ms = _probe_duration_ms(seg_wav)
                else:
                    # 3) TTS -> mp3
                    seg_mp3 = synthesize_speech_to_local_mp3(
                        text=spoken,
                        language=target_language,
                        voice_id=voice_id,
                        gender=gender,
                        out_dir=tmpdir,
                        name_hint=f"seg_{idx:05d}_a{attempt}",
                    )

                    # 4) mp3 -> wav
                    seg_wav = os.path.join(tmpdir, f"seg_{idx:05d}_a{attempt}.wav")
                    _mp3_to_wav(seg_mp3, seg_wav)

                    real_ms = _probe_duration_ms(seg_wav)

                    # Cache only sane audio
                    if real_ms > 120:
                        cache.set(cache_key, seg_wav, VOICE_CUE_CACHE_TTL)

                # Keep best candidate
                if best_ms is None:
                    best_ms, best_wav = real_ms, seg_wav
                else:
                    def score(ms: int) -> float:
                        if ms <= slot_ms:
                            return abs(slot_ms - ms)
                        return abs(ms - slot_ms) + 999999

                    if score(real_ms) < score(best_ms):
                        best_ms, best_wav = real_ms, seg_wav

                # Classify quality
                reason = _classify_voice_result(
                    real_ms=real_ms,
                    slot_ms=slot_ms,
                    overrun_tolerance=OVERRUN_TOLERANCE,
                )

                # Stop early if acceptable
                if reason == VoiceFailReason.ACCEPTABLE:
                    break

                # Smart retry decision (Stage 4)
                if not _should_retry_voice(reason=reason, attempt=attempt):
                    break


            # Fallback: silence
            if not best_wav or best_ms is None:
                fitted_wav = os.path.join(tmpdir, f"fit_{idx:05d}.wav")
                _make_silence_wav(fitted_wav, slot_ms)
                wav_parts.append(fitted_wav)
                cursor_ms = max(cursor_ms, cue.end_ms)
                continue

            # 5) Fit best wav into slot
            fitted_wav = os.path.join(tmpdir, f"fit_{idx:05d}.wav")

            if best_ms <= 0:
                _make_silence_wav(fitted_wav, slot_ms)

            elif best_ms < slot_ms:
                pad_wav = os.path.join(tmpdir, f"pad_{idx:05d}.wav")
                _make_silence_wav(pad_wav, slot_ms - best_ms)
                join_wav = os.path.join(tmpdir, f"join_{idx:05d}.wav")
                _concat_wavs([best_wav, pad_wav], join_wav)
                shutil.move(join_wav, fitted_wav)

            elif best_ms > slot_ms:
                speed = best_ms / float(slot_ms)

                if speed <= MAX_SPEEDUP:
                    sped = os.path.join(tmpdir, f"sped_{idx:05d}.wav")
                    _speedup_wav(best_wav, sped, speed)
                    _trim_wav_to_ms(sped, fitted_wav, slot_ms)
                else:
                    _trim_wav_to_ms(best_wav, fitted_wav, slot_ms)
            else:
                shutil.copyfile(best_wav, fitted_wav)

            wav_parts.append(fitted_wav)
            cursor_ms = max(cursor_ms, cue.end_ms)

        # Tail silence
        timeline_end = max(c.end_ms for c in cues)
        tail_ms = max(0, timeline_end - cursor_ms)
        if tail_ms > 0:
            tail = os.path.join(tmpdir, "tail.wav")
            _make_silence_wav(tail, tail_ms)
            wav_parts.append(tail)
            cursor_ms += tail_ms

        if not wav_parts:
            raise RuntimeError("No voice parts generated")

        # 6) Final concat
        final_wav = os.path.join(tmpdir, "final.wav")
        _concat_wavs(wav_parts, final_wav)

        final_mp3 = os.path.join(tmpdir, "final.mp3")
        _wav_to_mp3(final_wav, final_mp3)

        duration_ms = _probe_duration_ms(final_mp3)
        return final_mp3, duration_ms

    finally:
        # Caller handles tmpdir cleanup
        pass



def save_local_file_to_storage(*, local_path: str, storage_path: str) -> str:
    """Save local file to default_storage, returns storage_path."""
    with open(local_path, "rb") as rf:
        default_storage.save(storage_path, rf)
    return storage_path
