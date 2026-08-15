# apps/posts/services/journeys/journey_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from dataclasses import dataclass

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety
from apps.creative_editor.models import CreativeComposition


@dataclass(frozen=True)
class JourneyDocumentText:
    """
    Visible user-authored text extracted from one Creative document.
    """

    layer_count: int
    texts: tuple[str, ...]

    @property
    def combined_text(self) -> str:
        return "\n\n".join(
            text
            for text in self.texts
            if text
        ).strip()

    @property
    def has_text(self) -> bool:
        return bool(
            self.combined_text
        )


def extract_journey_document_text(
    document: dict,
) -> JourneyDocumentText:
    """
    Extract visible text layers in visual z-order.

    Hidden layers are ignored because they are not rendered into
    the published Journey output.
    """

    if not isinstance(
        document,
        dict,
    ):
        return JourneyDocumentText(
            layer_count=0,
            texts=(),
        )

    layers = document.get(
        "layers"
    )

    if not isinstance(
        layers,
        list,
    ):
        return JourneyDocumentText(
            layer_count=0,
            texts=(),
        )

    text_layers: list[
        tuple[int, int, str]
    ] = []

    for index, layer in enumerate(
        layers
    ):
        if not isinstance(
            layer,
            dict,
        ):
            continue

        if layer.get(
            "type"
        ) != "text":
            continue

        if layer.get(
            "is_hidden",
            False,
        ):
            continue

        content = layer.get(
            "content"
        )

        if not isinstance(
            content,
            dict,
        ):
            continue

        text = content.get(
            "text"
        )

        if not isinstance(
            text,
            str,
        ):
            continue

        cleaned = text.strip()

        if not cleaned:
            continue

        z_index = layer.get(
            "z_index",
            index,
        )

        if (
            isinstance(
                z_index,
                bool,
            )
            or not isinstance(
                z_index,
                int,
            )
        ):
            z_index = index

        text_layers.append(
            (
                z_index,
                index,
                cleaned,
            )
        )

    text_layers.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    texts = tuple(
        item[2]
        for item in text_layers
    )

    return JourneyDocumentText(
        layer_count=len(
            texts
        ),
        texts=texts,
    )


def enforce_journey_composition_content_safety(
    *,
    composition: CreativeComposition,
    actor,
) -> None:
    """
    Enforce Content Safety for all visible Journey text.

    All visible text layers are inspected together so harmful text
    cannot bypass moderation by splitting one phrase across layers.
    """

    extracted = extract_journey_document_text(
        composition.document
        or {}
    )

    if not extracted.has_text:
        return

    enforce_text_safety(
        text=extracted.combined_text,
        context=SafetyContext.JOURNEY_TEXT,
        actor=actor,
        field_name="document.text_layers",
    )

def enforce_journey_close_content_safety(
    *,
    text: str,
    is_private: bool,
    actor,
) -> None:
    """
    Enforce Content Safety for a publicly visible Journey Close.

    Private Journey Close text is owner-only and is not public UGC.
    """

    if is_private:
        return

    clean_text = str(
        text
        or ""
    ).strip()

    if not clean_text:
        return

    enforce_text_safety(
        text=clean_text,
        context=SafetyContext.JOURNEY_TEXT,
        actor=actor,
        field_name="close_text",
    )

def enforce_owned_journey_composition_content_safety(
    *,
    composition_id,
    actor,
) -> None:
    """
    Resolve and inspect one active user-owned Journey composition.

    Missing or foreign compositions are intentionally ignored here.
    Existing Journey ownership validation remains authoritative and
    will return its canonical validation error afterward.
    """

    if (
        actor is None
        or not getattr(
            actor,
            "is_authenticated",
            False,
        )
    ):
        return

    composition = (
        CreativeComposition.objects
        .filter(
            public_id=composition_id,
            owner=actor,
            is_active=True,
        )
        .only(
            "id",
            "public_id",
            "owner_id",
            "document",
        )
        .first()
    )

    if composition is None:
        return

    enforce_journey_composition_content_safety(
        composition=composition,
        actor=actor,
    )