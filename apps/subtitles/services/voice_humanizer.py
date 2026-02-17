# apps/subtitles/services/voice_humanizer.py

from __future__ import annotations

import logging
import re
import hashlib
import json
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```.*?\n|```$", flags=re.DOTALL)
_QUOTES_RE = re.compile(r'^[\"\u201c\u201d]+|[\"\u201c\u201d]+$')
_WS_RE = re.compile(r"\s+")
_SENT_BOUNDARY_RE = re.compile(r"[.!?؟…]\s")

# Cache TTL (seconds)
VOICE_HUMANIZE_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days


def _clean_output(s: str) -> str:
    out = (s or "").strip()
    out = _FENCE_RE.sub("", out).strip()
    out = _QUOTES_RE.sub("", out).strip()
    out = _WS_RE.sub(" ", out).strip()
    return out


def _clamp(text: str, limit: Optional[int]) -> str:
    s = (text or "").strip()
    if not s or not limit or limit <= 0:
        return s
    if len(s) <= limit:
        return s

    matches = list(_SENT_BOUNDARY_RE.finditer(s[:limit]))
    if matches:
        cut = matches[-1].end()
        return s[:cut].strip()

    ws = s.rfind(" ", 0, limit)
    if ws > 40:
        return s[:ws].strip()

    return s[:limit].strip()


def _should_skip_llm(src: str, max_chars: Optional[int]) -> bool:
    if not src:
        return True
    s = src.strip()
    if len(s) < 18:
        return True
    if max_chars and len(s) <= max_chars:
        return True
    return False


def _cache_key(*, text: str, language: str, max_chars: Optional[int], tone_profile: Optional[dict]) -> str:
    payload = {
        "text": text,
        "lang": language,
        "max": max_chars,
        "tone": tone_profile or {},
        "model": getattr(settings, "OPENAI_VOICE_HUMANIZE_MODEL", ""),
        "prompt": "v1",  # bump if you change rules
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"voice:humanize:{h}"


def humanize_for_voice(*, text: str, language: str, max_chars: int | None = None, tone_profile: dict | None = None) -> str:
    src = _clean_output(text or "")
    if not src:
        return src

    # Skip LLM if unnecessary
    if _should_skip_llm(src, max_chars):
        return _clamp(src, max_chars)

    # Feature / key gate
    if not getattr(settings, "VOICE_HUMANIZE_ENABLED", True):
        return _clamp(src, max_chars)
    if not getattr(settings, "OPENAI_API_KEY", None):
        return _clamp(src, max_chars)

    # ---------- CACHE ----------
    key = _cache_key(
        text=src,
        language=language,
        max_chars=max_chars,
        tone_profile=tone_profile,
    )
    cached = cache.get(key)
    if cached:
        return _clamp(cached, max_chars)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        model = getattr(
            settings,
            "OPENAI_VOICE_HUMANIZE_MODEL",
            getattr(settings, "OPENAI_TRANSLATION_MODEL", "gpt-4o-mini"),
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional speech editor.\n"
                    "Rewrite text for natural spoken delivery.\n"
                    "Rules:\n"
                    "- Do NOT change meaning.\n"
                    "- Do NOT add new details.\n"
                    "- Keep it short and easy to speak.\n"
                    "- Do NOT output quotes or markdown.\n"
                    "- Output ONLY the spoken version.\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {language}\n"
                    f"Soft limit: ~{max_chars} chars\n\n"
                    f"Text:\n{src}"
                ),
            },
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )

        out = _clean_output(resp.choices[0].message.content or "")
        if not out:
            out = src

        cache.set(key, out, VOICE_HUMANIZE_CACHE_TTL)
        return _clamp(out, max_chars)

    except Exception:
        logger.exception("[voice] humanize_for_voice failed")
        return _clamp(src, max_chars)
