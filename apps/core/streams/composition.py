# apps/core/streams/composition.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from apps.core.streams.constants import STREAM_SCOPE_SQUARE


SUGGESTED_USERS_ELIGIBLE_EXTENSIONS = frozenset({
    0,
    2,
})

SUGGESTED_USERS_LIMIT = 7

SUGGESTED_USERS_MIN_AFTER_ITEM_POSITION = 2
SUGGESTED_USERS_MAX_AFTER_ITEM_POSITION = 6

_SUGGESTED_USERS_PLACEMENT_VERSION = "v1"


@dataclass(frozen=True)
class SuggestedUsersPlacement:
    """
    Server-owned placement for a suggested-users module.

    `after_item_position` is one-based and refers to Stream content items.
    The module is inserted after content item 2 through 6.
    """

    after_item_position: int
    user_limit: int = SUGGESTED_USERS_LIMIT


class StreamCompositionPolicy:
    """
    Composition policy for non-content modules inside Streams.

    Content batches remain seven Stream items.
    Suggested-user modules are inserted between content items and do not
    consume a Stream content slot.
    """

    @classmethod
    def suggested_users_placement(
        cls,
        *,
        context,
    ) -> SuggestedUsersPlacement | None:
        if context.scope != STREAM_SCOPE_SQUARE:
            return None

        extension = cls._normalized_positive_int(
            getattr(
                context,
                "extension",
                0,
            ),
            allow_zero=True,
        )

        if extension not in SUGGESTED_USERS_ELIGIBLE_EXTENSIONS:
            return None

        viewer = getattr(
            context,
            "viewer",
            None,
        )

        if not viewer or not getattr(
            viewer,
            "is_authenticated",
            False,
        ):
            return None

        viewer_id = cls._normalized_positive_int(
            getattr(
                viewer,
                "id",
                None,
            )
        )

        seed_id = cls._normalized_positive_int(
            getattr(
                context,
                "seed_id",
                None,
            )
        )

        if viewer_id is None or seed_id is None:
            return None

        kind = str(
            getattr(
                context,
                "kind",
                "",
            )
            or ""
        ).strip()

        after_item_position = cls._stable_after_item_position(
            viewer_id=viewer_id,
            seed_id=seed_id,
            extension=extension,
            kind=kind,
        )

        return SuggestedUsersPlacement(
            after_item_position=after_item_position,
        )

    @staticmethod
    def _stable_after_item_position(
        *,
        viewer_id: int,
        seed_id: int,
        extension: int,
        kind: str,
    ) -> int:
        key = (
            f"{_SUGGESTED_USERS_PLACEMENT_VERSION}:"
            f"{viewer_id}:"
            f"{seed_id}:"
            f"{extension}:"
            f"{kind}"
        )

        digest = sha256(
            key.encode("utf-8")
        ).digest()

        position_count = (
            SUGGESTED_USERS_MAX_AFTER_ITEM_POSITION
            - SUGGESTED_USERS_MIN_AFTER_ITEM_POSITION
            + 1
        )

        offset = int.from_bytes(
            digest[:4],
            byteorder="big",
            signed=False,
        ) % position_count

        return (
            SUGGESTED_USERS_MIN_AFTER_ITEM_POSITION
            + offset
        )

    @staticmethod
    def _normalized_positive_int(
        value,
        *,
        allow_zero: bool = False,
    ) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None

        minimum = 0 if allow_zero else 1

        if parsed < minimum:
            return None

        return parsed