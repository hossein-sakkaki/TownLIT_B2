# apps/subtitles/services/prompt_builder_transcript.py

from __future__ import annotations

def build_transcript_humanize_prompt(*, language: str, raw_text: str) -> list[dict]:
    # Short, strict, non-creative transcript cleanup prompt
    return [
        {
            "role": "system",
            "content": (
                "You are a professional transcription editor.\n"
                "Task: correct ASR transcript text with maximum fidelity.\n"
                "Rules:\n"
                "- Do NOT add new meaning or new facts.\n"
                "- Do NOT paraphrase or rewrite style.\n"
                "- Fix misheard words, punctuation, casing, spacing.\n"
                "- Keep faith terms consistent.\n"
                "- Keep names and Bible references as-is when possible.\n"
                "- Output ONLY the corrected transcript text.\n"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Language: {language}\n\n"
                "Raw transcript:\n"
                f"{raw_text}\n\n"
                "Return the corrected transcript only."
            ),
        },
    ]
