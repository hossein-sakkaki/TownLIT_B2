# apps/core/streams/engine.py

from django.db.models import QuerySet

from apps.core.streams.constants import (
    STREAM_KIND_TESTIMONY,
    STREAM_KIND_MOMENT,
    STREAM_KIND_PRAY,
    STREAM_MODE_RECENT,
    STREAM_SCOPE_SQUARE,
    STREAM_SCOPE_PROFILE,
    STREAM_SCOPE_OWNER,
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_IMAGE,
    STREAM_SUBTYPE_WRITTEN,
    STREAM_PAGE_SIZE,
    STREAM_SQUARE_PAGE_SIZE,
    STREAM_SCOPE_MESSENGER,
    STREAM_LIMITED_EXTENSION_SCOPES,
)
from apps.core.streams.dto import StreamItem, StreamPage
from apps.core.streams.query import StreamQuery
from apps.core.streams.tiers.registry import get_stream_tiers


class StreamEngine:
    """
    Universal stream engine.

    Important:
    - Square streams use extension-based paging to avoid addictive hidden
      infinite scroll.
    - Square streams fill missing slots from safe subtype fallbacks inside
      the same kind.
    - Profile/Owner streams can also fill from subtype fallbacks inside
      the same kind, but they keep cursor-based pagination.
    """

    @staticmethod
    def build_page(
        *,
        context,
        source,
        seed,
        subtype: str,
    ) -> StreamPage:
        """
        Build final stream page.
        """

        is_first_page = StreamEngine._is_first_page(
            context=context,
        )

        effective_limit = StreamEngine._effective_limit(
            context=context,
            is_first_page=is_first_page,
        )

        effective_offset = StreamEngine._effective_offset(
            context=context,
        )

        used_ids: set[int] = {seed.id}

        objects = StreamEngine._build_objects(
            context=context,
            source=source,
            seed=seed,
            seed_subtype=subtype,
            limit=effective_limit,
            offset=effective_offset,
            used_ids=used_ids,
        )

        items: list[StreamItem] = []

        if is_first_page:
            items.append(
                StreamItem(
                    kind=context.kind,
                    obj=seed,
                )
            )

        for obj in objects:
            items.append(
                StreamItem(
                    kind=context.kind,
                    obj=obj,
                )
            )

        return StreamPage(
            items=items,
            next_cursor=StreamEngine._build_next_cursor(
                items,
                context=context,
            ),
            kind=context.kind,
            subtype=subtype,
            scope=context.scope,
            mode=context.mode,
            extension=context.extension,
            can_continue=True,
        )

    @staticmethod
    def _build_objects(
        *,
        context,
        source,
        seed,
        seed_subtype: str,
        limit: int,
        offset: int,
        used_ids: set[int],
    ) -> list:
        """
        Build stream objects.
        """

        subtype_pool = StreamEngine._subtype_pool(
            context=context,
            seed_subtype=seed_subtype,
        )

        results: list = []
        skipped = 0

        for subtype in subtype_pool:
            if len(results) >= limit:
                break

            qs = StreamQuery.build(
                model=source.model,
                viewer=context.viewer,
                seed=seed,
                subtype=subtype,
                scope=context.scope,
                requires_conversion=source.requires_conversion,
            )

            objects, skipped = StreamEngine._consume_queryset_with_skip_state(
                qs=qs,
                context=context,
                seed=seed,
                limit=limit - len(results),
                offset=offset,
                already_skipped=skipped,
                used_ids=used_ids,
            )

            results.extend(objects)

        return results[:limit]

    @staticmethod
    def _subtype_pool(
        *,
        context,
        seed_subtype: str,
    ) -> list[str]:
        """
        Return deterministic subtype order.
        """

        if context.kind == STREAM_KIND_TESTIMONY:
            base = [
                STREAM_SUBTYPE_VIDEO,
                STREAM_SUBTYPE_AUDIO,
                STREAM_SUBTYPE_WRITTEN,
            ]

            return StreamEngine._ordered_pool(
                seed_subtype=seed_subtype,
                fallback=base,
            )

        if context.kind in {STREAM_KIND_MOMENT, STREAM_KIND_PRAY}:
            if context.scope in {
                STREAM_SCOPE_SQUARE,
                STREAM_SCOPE_MESSENGER,
                STREAM_SCOPE_PROFILE,
                STREAM_SCOPE_OWNER,
            }:
                base = [
                    STREAM_SUBTYPE_IMAGE,
                    STREAM_SUBTYPE_VIDEO,
                ]

                return StreamEngine._ordered_pool(
                    seed_subtype=seed_subtype,
                    fallback=base,
                )

        return [seed_subtype]

    @staticmethod
    def _ordered_pool(
        *,
        seed_subtype: str,
        fallback: list[str],
    ) -> list[str]:
        output: list[str] = []

        if seed_subtype:
            output.append(seed_subtype)

        for subtype in fallback:
            if subtype not in output:
                output.append(subtype)

        return output

    @staticmethod
    def _is_first_page(*, context) -> bool:
        """
        A true first page has no cursor and extension=0.

        Profile streams keep extension=0 while using cursor pagination, so
        cursor pages must not be treated as first pages.
        """

        extension = max(
            int(context.extension or 0),
            0,
        )

        return extension == 0 and context.cursor is None

    @staticmethod
    def _effective_limit(
        *,
        context,
        is_first_page: bool,
    ) -> int:
        """
        Keep first page total stable:
        first page => seed + page_size - 1
        next pages => page_size
        """

        page_size = StreamEngine._page_size(
            context=context,
        )

        if is_first_page:
            return max(page_size - 1, 0)

        return page_size

    @staticmethod
    def _effective_offset(*, context) -> int:
        """
        Square uses extension-based paging with no cursor.

        With page size 7:
        extension=0 consumes 6 related items after seed.
        extension=1 skips 6 and takes 7.
        extension=2 skips 13 and takes 7.
        """

        if context.scope not in STREAM_LIMITED_EXTENSION_SCOPES:
            return 0

        extension = max(
            int(context.extension or 0),
            0,
        )

        if extension <= 0:
            return 0

        first_page_related_count = max(
            STREAM_SQUARE_PAGE_SIZE - 1,
            0,
        )

        return first_page_related_count + (
            (extension - 1) * STREAM_SQUARE_PAGE_SIZE
        )

    @staticmethod
    def _page_size(*, context) -> int:
        if context.scope in STREAM_LIMITED_EXTENSION_SCOPES:
            return STREAM_SQUARE_PAGE_SIZE

        return STREAM_PAGE_SIZE

    @staticmethod
    def _consume_queryset_with_skip_state(
        *,
        qs: QuerySet,
        context,
        seed,
        limit: int,
        offset: int,
        already_skipped: int,
        used_ids: set[int],
    ) -> tuple[list, int]:
        """
        Consume queryset by mode while carrying skip state. 
        """

        if context.scope not in STREAM_LIMITED_EXTENSION_SCOPES:
            qs = StreamQuery.apply_cursor(
                qs=qs,
                cursor=context.cursor,
            )

        if context.mode == STREAM_MODE_RECENT:
            return StreamEngine._consume_recent(
                qs=qs,
                limit=limit,
                offset=offset,
                already_skipped=already_skipped,
                used_ids=used_ids,
            )

        return StreamEngine._consume_related(
            qs=qs,
            context=context,
            seed=seed,
            limit=limit,
            offset=offset,
            already_skipped=already_skipped,
            used_ids=used_ids,
        )

    @staticmethod
    def _consume_recent(
        *,
        qs: QuerySet,
        limit: int,
        offset: int,
        already_skipped: int,
        used_ids: set[int],
    ) -> tuple[list, int]:
        """
        Consume by recent order.
        """

        qs = qs.order_by("-published_at", "-id")
        results: list = []
        skipped = already_skipped

        fetch_window = max(
            (offset + limit) * 4,
            limit * 4,
            32,
        )

        for obj in qs[:fetch_window]:
            if obj.id in used_ids:
                continue

            if skipped < offset:
                skipped += 1
                used_ids.add(obj.id)
                continue

            results.append(obj)
            used_ids.add(obj.id)

            if len(results) >= limit:
                break

        return results, skipped

    @staticmethod
    def _consume_related(
        *,
        qs: QuerySet,
        context,
        seed,
        limit: int,
        offset: int,
        already_skipped: int,
        used_ids: set[int],
    ) -> tuple[list, int]:
        """
        Consume by related tiers.
        """

        results: list = []
        skipped = already_skipped
        tiers = get_stream_tiers(context.kind)

        for tier in tiers:
            if len(results) >= limit:
                break

            tier_qs = tier.build_queryset(
                base_qs=qs,
                seed=seed,
                viewer=context.viewer,
                used_ids=used_ids,
            ).order_by("-published_at", "-id")

            tier_limit = max(
                (offset + limit) * 4,
                limit * 4,
                getattr(tier, "limit", limit),
                32,
            )

            for obj in tier_qs[:tier_limit]:
                if obj.id in used_ids:
                    continue

                if skipped < offset:
                    skipped += 1
                    used_ids.add(obj.id)
                    continue

                results.append(obj)
                used_ids.add(obj.id)

                if len(results) >= limit:
                    break

        return results[:limit], skipped

    @staticmethod
    def _build_next_cursor(
        items: list[StreamItem],
        *,
        context,
    ) -> str | None:
        """
        Build cursor from last item.

        Square intentionally does not expose cursor because it uses explicit
        extension-based continuation only.
        """

        if context.scope in STREAM_LIMITED_EXTENSION_SCOPES:
            return None

        if not items:
            return None

        last_obj = items[-1].obj

        published_at = getattr(last_obj, "published_at", None)
        object_id = getattr(last_obj, "id", None)

        if not published_at or not object_id:
            return None

        return f"{published_at.isoformat()}|{object_id}"