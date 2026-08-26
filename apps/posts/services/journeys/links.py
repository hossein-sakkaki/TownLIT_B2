# apps/posts/services/journeys/links.py

from __future__ import annotations

from urllib.parse import quote, urlencode


def build_journey_entry_link(
    *,
    entry_slug: str,
    entry_id: int | None = None,
    journey_id: int | None = None,
    focus: str | None = None,
    extra_params: dict | None = None,
) -> str:
    """
    Build TownLIT's canonical JourneyEntry deep link.

    Important:
    - The JourneyEntry slug is the primary navigation identity.
    - entry_id is an integrity/debug hint.
    - journey_id is parent context only.
    - Clients must never use journey_id or owner identity to resolve
      a different/latest JourneyEntry when the exact entry is unavailable.
    """

    normalized_slug = str(
        entry_slug or ""
    ).strip()

    if not normalized_slug:
        raise ValueError(
            "JourneyEntry slug is required."
        )

    params: dict[str, str] = {
        "kind": "journey",
    }

    if entry_id is not None:
        params["entry_id"] = str(
            int(entry_id)
        )

    if journey_id is not None:
        params["journey_id"] = str(
            int(journey_id)
        )

    normalized_focus = str(
        focus or ""
    ).strip()

    if normalized_focus:
        params["focus"] = normalized_focus

    if isinstance(extra_params, dict):
        for key, value in extra_params.items():
            if value is None:
                continue

            normalized_key = str(
                key or ""
            ).strip()

            if not normalized_key:
                continue

            params[normalized_key] = str(
                value
            )

    encoded_slug = quote(
        normalized_slug,
        safe="",
    )

    return (
        f"/journey/{encoded_slug}?"
        f"{urlencode(params)}"
    )