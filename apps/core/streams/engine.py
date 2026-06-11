# apps/core/streams/engine.py

from random import shuffle

from django.db.models import QuerySet

from apps.core.streams.constants import (
    STREAM_KIND_TESTIMONY,
    STREAM_MODE_RECENT,
    TESTIMONY_FALLBACK_SUBTYPES,
    STREAM_PAGE_SIZE,
)
from apps.core.streams.dto import StreamItem, StreamPage
from apps.core.streams.query import StreamQuery
from apps.core.streams.tiers.registry import get_stream_tiers


class StreamEngine:
    """
    Universal stream engine.
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

        effective_limit = StreamEngine._effective_limit(context=context)
        used_ids: set[int] = {seed.id}

        if context.kind == STREAM_KIND_TESTIMONY:
            objects = StreamEngine._build_testimony_objects(
                context=context,
                source=source,
                seed=seed,
                seed_subtype=subtype,
                limit=effective_limit,
                used_ids=used_ids,
            )
        else:
            qs = StreamQuery.build(
                model=source.model,
                viewer=context.viewer,
                seed=seed,
                subtype=subtype,
                scope=context.scope,
                requires_conversion=source.requires_conversion,
            )

            objects = StreamEngine._consume_queryset(
                qs=qs,
                context=context,
                seed=seed,
                limit=effective_limit,
                used_ids=used_ids,
            )

        items: list[StreamItem] = []

        if context.is_first_page:
            items.append(StreamItem(kind=context.kind, obj=seed))

        for obj in objects:
            items.append(StreamItem(kind=context.kind, obj=obj))

        return StreamPage(
            items=items,
            next_cursor=StreamEngine._build_next_cursor(items),
            kind=context.kind,
            subtype=subtype,
            scope=context.scope,
            mode=context.mode,
            extension=context.extension,
            can_continue=True,
        )

    @staticmethod
    def _effective_limit(*, context) -> int:
        """
        Keep first page total stable.
        """

        return STREAM_PAGE_SIZE - (1 if context.is_first_page else 0)

    @staticmethod
    def _build_testimony_objects(
        *,
        context,
        source,
        seed,
        seed_subtype: str,
        limit: int,
        used_ids: set[int],
    ) -> list:
        """
        Build testimony stream with subtype fallback.
        """

        fallback = [
            subtype
            for subtype in TESTIMONY_FALLBACK_SUBTYPES
            if subtype != seed_subtype
        ]

        shuffle(fallback)

        subtype_pool = [seed_subtype] + fallback

        results: list = []
        remaining = limit

        for subtype in subtype_pool:
            if remaining <= 0:
                break

            qs = StreamQuery.build(
                model=source.model,
                viewer=context.viewer,
                seed=seed,
                subtype=subtype,
                scope=context.scope,
                requires_conversion=source.requires_conversion,
            )

            objects = StreamEngine._consume_queryset(
                qs=qs,
                context=context,
                seed=seed,
                limit=remaining,
                used_ids=used_ids,
            )

            results.extend(objects)
            remaining = limit - len(results)

        return results[:limit]

    @staticmethod
    def _consume_queryset(
        *,
        qs: QuerySet,
        context,
        seed,
        limit: int,
        used_ids: set[int],
    ) -> list:
        """
        Consume queryset by mode.
        """

        qs = StreamQuery.apply_cursor(
            qs=qs,
            cursor=context.cursor,
        )

        if context.mode == STREAM_MODE_RECENT:
            return StreamEngine._consume_recent(
                qs=qs,
                limit=limit,
                used_ids=used_ids,
            )

        return StreamEngine._consume_related(
            qs=qs,
            context=context,
            seed=seed,
            limit=limit,
            used_ids=used_ids,
        )

    @staticmethod
    def _consume_recent(
        *,
        qs: QuerySet,
        limit: int,
        used_ids: set[int],
    ) -> list:
        """
        Consume by recent order.
        """

        qs = qs.order_by("-published_at", "-id")
        results: list = []

        for obj in qs[: limit * 3]:
            if obj.id in used_ids:
                continue

            results.append(obj)
            used_ids.add(obj.id)

            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _consume_related(
        *,
        qs: QuerySet,
        context,
        seed,
        limit: int,
        used_ids: set[int],
    ) -> list:
        """
        Consume by related tiers.
        """

        results: list = []
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

            tier_limit = max(limit * 2, getattr(tier, "limit", limit))

            for obj in tier_qs[:tier_limit]:
                if obj.id in used_ids:
                    continue

                results.append(obj)
                used_ids.add(obj.id)

                if len(results) >= limit:
                    break

        return results[:limit]

    @staticmethod
    def _build_next_cursor(items: list[StreamItem]) -> str | None:
        """
        Build cursor from last item.
        """

        if not items:
            return None

        last_obj = items[-1].obj

        published_at = getattr(last_obj, "published_at", None)
        object_id = getattr(last_obj, "id", None)

        if not published_at or not object_id:
            return None

        return f"{published_at.isoformat()}|{object_id}"
    
