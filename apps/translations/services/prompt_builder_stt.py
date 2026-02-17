# apps/translations/services/prompt_builder_stt.py

def build_stt_cleanup_prompt(
    *,
    source_text: str,
    language: str,
) -> list[dict]:
    system_prompt = (
        "You are a professional speech-to-text editor.\n\n"
        "You are given raw speech transcription produced by an AI system.\n\n"
        "Your task:\n"
        "- Fix obvious speech recognition errors\n"
        "- Correct misheard words using context\n"
        "- Remove filler words (uh, um, repeated starts)\n"
        "- Merge broken sentences naturally\n\n"
        "Strict rules:\n"
        "- Do NOT add new ideas or information\n"
        "- Do NOT rewrite or paraphrase creatively\n"
        "- Do NOT polish style or make it literary\n"
        "- Preserve the speaker's original tone and intent\n\n"
        f"Language: {language}\n\n"
        "Output rules:\n"
        "- Return ONLY the corrected transcript\n"
        "- No explanations, no formatting"
    )

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "RAW TRANSCRIPT:\n"
                f"{source_text}\n\n"
                "TASK:\n"
                "Return the corrected transcript."
            ),
        },
    ]
