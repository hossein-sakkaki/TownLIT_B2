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
from apps.core.boundaries.query import BoundaryVisibilityQuery
from apps.profiles.selectors.friends import get_friend_user_ids
from apps.subtitles.services.testimony_enforcement import (
    filter_testimony_queryset_for_public_feeds,
)

logger = logging.getLogger(__name__)


class SquareQuery:
    """
    Unified Square feed query builder.

    Responsibilities:
    - source selection
    - media/conversion availability
    - visibility policy
    - owner visibility policy
    - Boundary visibility policy
    - Square UI policy: exclude viewer-owned content
    - friends tab filtering
    - square metadata annotations

    Stillness policy:
    - Stillness does NOT remove content from Square.
    - It only suppresses interruptions/notifications elsewhere.

    Boundary policy:
    - Boundary removes content owned by users where Boundary exists
      in either direction between viewer and owner.
    """

    @staticmethod
    def build(*, viewer, kind: str = SQUARE_KIND_ALL) -> List[QuerySet]:
        # -------------------------------------------------
        # 0) Friends scope precompute
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
            # 1) Kind filter
            # ---------------------------------------------
            if (
                kind not in (SQUARE_KIND_ALL, SQUARE_KIND_FRIENDS)
                and source.kind != kind
            ):
                continue

            qs = model.objects.all()

            # ---------------------------------------------
            # 2) Availability / conversion
            # ---------------------------------------------
            if source.requires_conversion:
                qs = qs.filter(is_converted=True)

            # ---------------------------------------------
            # 3) Media existence filter
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
            # 4) Testimony review public-feed policy
            # ---------------------------------------------
            if source.kind == "testimony":
                qs = filter_testimony_queryset_for_public_feeds(qs)

            # ---------------------------------------------
            # 5) Visibility filtering
            # ---------------------------------------------
            qs = VisibilityQuery.for_viewer(
                viewer=viewer,
                base_queryset=qs,
            )

            # ---------------------------------------------
            # 6) Owner visibility filtering
            # ---------------------------------------------
            qs = OwnerVisibilityQuery.filter_queryset_for_square(
                qs,
                viewer=viewer,
                kind=kind,
            )

            # ---------------------------------------------
            # 7) Boundary visibility filtering
            # ---------------------------------------------
            qs = BoundaryVisibilityQuery.exclude_boundary_conflicts(
                qs,
                viewer=viewer,
            )

            # ---------------------------------------------
            # 8) Exclude viewer-owned content
            # Square discovery policy:
            # user should not see their own content in Square.
            # ---------------------------------------------
            qs = exclude_owned_by_viewer(
                qs,
                viewer,
            )

            # ---------------------------------------------
            # 9) Friends scope
            # ---------------------------------------------
            if kind == SQUARE_KIND_FRIENDS:
                qs = qs.filter(
                    owner_q_for_user_ids(user_ids=friend_ids)
                )

            # ---------------------------------------------
            # 10) Annotate square metadata
            # ---------------------------------------------
            qs = qs.annotate(
                square_kind=models.Value(
                    source.kind,
                    output_field=models.CharField(),
                ),
                square_ct=models.Value(
                    ContentType.objects.get_for_model(model).id,
                    output_field=models.IntegerField(),
                ),
            )

            querysets.append(qs)

        return querysets
    
    
    
