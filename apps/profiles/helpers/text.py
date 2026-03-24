# apps/profiles/helpers/text.py

ACRONYMS = {"it", "ai", "tv"}


def humanize_service_code(code: str) -> str:
    """Title-case with acronym preservation."""
    if not code:
        return ""

    s = code.replace("_", " ").strip()
    parts = []

    for p in s.split():
        lp = p.lower()
        parts.append(lp.upper() if lp in ACRONYMS else (p[:1].upper() + p[1:].lower()))

    return " ".join(parts)