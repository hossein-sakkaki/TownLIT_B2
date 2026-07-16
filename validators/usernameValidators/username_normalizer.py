# validators/usernameValidators/username_normalizer.py

import re


def normalize_username(value: str | None) -> str:
    """
    Normalize username before validation and storage.

    Rules:
    - trim surrounding whitespace;
    - lowercase;
    - remove all remaining whitespace.

    Separator validation is handled separately by validate_username_format.
    """
    if value is None:
        return ""

    username = str(value).strip().lower()
    username = re.sub(r"\s+", "", username)

    return username


def compact_username(value: str) -> str:
    """
    Remove separators and other non-alphanumeric characters for safety checks.

    Examples:
        town_lit -> townlit
        t-o-w-n-l-i-t -> townlit
        a.d.m.i.n -> admin

    Although dots and hyphens are no longer valid username characters,
    compaction remains important for reserved-word and abuse detection.
    """
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower(),
    )