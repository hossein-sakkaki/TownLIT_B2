# apps/core/square/query.py

from __future__ import annotations

import logging
from typing import List

from django.db import models
from django.db.models import Q, QuerySet
from django.contrib.contenttypes.models import ContentType

from apps.core.square.constants import (
    SQUARE_KIND_ALL,
    SQUARE_KIND_FRIENDS,
    SQUARE_ALLOWED_MEDIA_KINDS,
)
from apps.core.ownership.ownership_filters import exclude_owned_by_viewer
from apps.core.ownership.ownership_predicates import owner_q_for_user_ids
from apps.core.square.registry import get_square_sources
from apps.core.visibility.query import VisibilityQuery
from apps.core.owner_visibility.query import OwnerVisibilityQuery
from apps.profiles.selectors.friends import get_friend_user_ids

logger = logging.getLogger(__name__)


class SquareQuery:
    """
    Unified Square feed query builder.
    Debug strategy:
    - Log counts at each filter stage to locate where items drop to zero.
    """

    @staticmethod
    def build(*, viewer, kind: str = SQUARE_KIND_ALL) -> List[QuerySet]:
        # -------------------------------------------------
        # 0) Friends scope precompute (only when needed)
        # -------------------------------------------------
        friend_ids: list[int] = []
        if kind == SQUARE_KIND_FRIENDS:
            if not viewer:
                return []

            friend_ids = get_friend_user_ids(viewer)

            if not friend_ids:
                return []

        querysets: List[QuerySet] = []

        for source in get_square_sources():
            model = source.model

            # ---------------------------------------------
            # 1) Kind filter (tabs)
            # ---------------------------------------------
            if kind not in (SQUARE_KIND_ALL, SQUARE_KIND_FRIENDS) and source.kind != kind:
                continue

            qs = model.objects.all()

            # ---------------------------------------------
            # 2) Availability (conversion-aware)
            # ---------------------------------------------
            if source.requires_conversion:
                qs = qs.filter(is_converted=True)

            # ---------------------------------------------
            # 3) Media existence filter (only if matched)
            # ---------------------------------------------
            media_q = Q()
            matched = False

            for field in source.media_fields:
                if field in SQUARE_ALLOWED_MEDIA_KINDS:
                    media_q |= Q(**{f"{field}__isnull": False})
                    matched = True

            if matched:
                qs = qs.filter(media_q)

            # ---------------------------------------------
            # 4) Visibility filtering (permission-level)
            # ---------------------------------------------
            qs = VisibilityQuery.for_viewer(viewer=viewer, base_queryset=qs)

            # OWNER VISIBILITY FILTER (BEFORE EXCLUDE OWNED)
            qs = OwnerVisibilityQuery.filter_queryset_for_square(
                qs,
                viewer=viewer,
                kind=kind,
            )

            # ---------------------------------------------
            # 5) Exclude own content (Square UI policy)
            # ---------------------------------------------
            qs = exclude_owned_by_viewer(qs, viewer)

            # ---------------------------------------------
            # 6) Friends scope (only for kind="friends")
            # ---------------------------------------------
            if kind == SQUARE_KIND_FRIENDS:
                qs = qs.filter(owner_q_for_user_ids(user_ids=friend_ids))

            # ---------------------------------------------
            # 7) Annotate square metadata
            # ---------------------------------------------
            qs = qs.annotate(
                square_kind=models.Value(source.kind, output_field=models.CharField()),
                square_ct=models.Value(
                    ContentType.objects.get_for_model(model).id,
                    output_field=models.IntegerField(),
                ),
            )
            querysets.append(qs)

        return querysets
