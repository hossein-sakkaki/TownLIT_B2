# apps/translations/services/prompt_builder.py

from __future__ import annotations


def build_humanize_prompt(
    *,
    source_text: str,
    translated_text: str,
    target_language: str,
    language_hints: list[str] | None = None,
) -> list[dict]:
    """
    Production-grade TownLIT humanization prompt.

    The caller may send either a complete text or one paragraph.
    Paragraph and line-break structure must be preserved.
    """

    system_prompt = (
        "You are a professional multilingual translation editor.\n\n"
        "Your role is NOT to translate again, but to gently refine an existing translation.\n\n"
        "Your goal:\n"
        "- Make the text sound natural, fluent, and human in modern everyday language\n"
        "- Keep a warm and respectful tone\n"
        "- Be spiritually sensitive ONLY where the original meaning requires it\n\n"
        "Strict rules:\n"
        "- Preserve the original meaning exactly\n"
        "- Do NOT add new ideas, explanations, or interpretations\n"
        "- Do NOT preach, sermonize, or sound theological or archaic\n"
        "- Do NOT exaggerate spiritual language\n"
        "- Do NOT shorten or expand the text\n"
        "- Preserve all paragraph boundaries and intentional line breaks\n"
        "- Do NOT merge separate paragraphs\n"
        "- Do NOT turn paragraphs into bullets unless the source already uses bullets\n\n"
        "Word choice guidance:\n"
        "- Prefer commonly used, contemporary expressions\n"
        "- If multiple correct words exist, choose the one that sounds most natural today\n"
        "- Use faith-sensitive terms ONLY if they are widely used and natural in daily language\n\n"
        f"Output rules:\n"
        f"- Return ONLY the final improved text in '{target_language}'\n"
        f"- Preserve the same paragraph and line-break structure as the input\n"
        f"- No quotes, no explanations, and no additional formatting"
    )

    user_prompt_parts = [
        "SOURCE TEXT (for meaning and structure reference):",
        source_text,
        "",
        "CURRENT TRANSLATION:",
        translated_text,
        "",
        "TASK:",
        (
            "Refine the CURRENT TRANSLATION to sound more natural and warm, "
            "while preserving the exact meaning and the same paragraph structure."
        ),
    ]

    if language_hints:
        user_prompt_parts.extend(
            [
                "",
                "OPTIONAL LANGUAGE HINTS (apply only if fully natural):",
                *[
                    f"- {hint}"
                    for hint in language_hints
                ],
            ]
        )

    user_prompt = "\n".join(
        user_prompt_parts
    )

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]