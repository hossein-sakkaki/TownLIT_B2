# apps/core/square/query.py

from __future__ import annotations

from typing import List

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import (
    Q, QuerySet, Exists, OuterRef, Value, BooleanField, CharField, IntegerField,
)
from django.utils import timezone

from apps.core.boundaries.query import BoundaryVisibilityQuery
from apps.core.owner_visibility.query import OwnerVisibilityQuery
from apps.core.ownership.ownership_filters import exclude_owned_by_viewer
from apps.core.ownership.ownership_predicates import owner_q_for_user_ids
from apps.core.square.constants import (
    SQUARE_ALLOWED_MEDIA_KINDS,
    SQUARE_FRIEND_AFFINITY_FIELD,
    SQUARE_KIND_ALL,
    normalize_square_kind,
)
from apps.core.square.registry import get_square_sources
from apps.core.visibility.query import VisibilityQuery
from apps.profiles.selectors.friends import get_friend_user_ids
from apps.subtitles.services.testimony_enforcement import (
    filter_testimony_queryset_for_public_feeds,
)


class SquareQuery:
    """
    Unified Square feed query builder.

    Responsibilities:
    - normalize legacy Square request kinds
    - source selection
    - media/conversion availability
    - visibility policy
    - owner visibility policy
    - Boundary visibility policy
    - exclude viewer-owned content
    - annotate relationship affinity for personalization
    - annotate Square metadata

    Friendship is a personalization signal, not a feed scope.

    Stillness does not remove content from Square.
    Boundary removes content between affected users.
    """

    @staticmethod
    def build(
        *,
        viewer,
        kind: str = SQUARE_KIND_ALL,
    ) -> List[QuerySet]:
        kind = normalize_square_kind(kind)

        friend_ids: list[int] = []

        if viewer:
            friend_ids = get_friend_user_ids(
                viewer
            )

        friend_owner_q = (
            owner_q_for_user_ids(
                user_ids=friend_ids
            )
            if friend_ids
            else None
        )

        querysets: List[QuerySet] = []

        for source in get_square_sources():
            model = source.model

            # ---------------------------------------------
            # 1) Source selection
            # ---------------------------------------------
            if (
                kind != SQUARE_KIND_ALL
                and source.kind != kind
            ):
                continue

            if source.kind == "organization_update":
                querysets.append(
                    SquareQuery._organization_updates(source, viewer=viewer)
                )
                continue

            qs = model.objects.all()

            # ---------------------------------------------
            # 2) Conversion availability
            # ---------------------------------------------
            if source.requires_conversion:
                qs = qs.filter(
                    is_converted=True
                )

            # ---------------------------------------------
            # 3) Media availability
            # ---------------------------------------------
            media_q = Q()
            matched = False

            for field in source.media_fields:
                if field not in SQUARE_ALLOWED_MEDIA_KINDS:
                    continue

                media_q |= Q(
                    **{
                        f"{field}__isnull": False,
                    }
                )

                matched = True

            if matched:
                qs = qs.filter(
                    media_q
                )

            # ---------------------------------------------
            # 4) Testimony public-feed policy
            # ---------------------------------------------
            if source.kind == "testimony":
                qs = filter_testimony_queryset_for_public_feeds(
                    qs
                )

            # ---------------------------------------------
            # 5) Content visibility
            # ---------------------------------------------
            qs = VisibilityQuery.for_viewer(
                viewer=viewer,
                base_queryset=qs,
            )

            # ---------------------------------------------
            # 6) Owner visibility
            # ---------------------------------------------
            qs = OwnerVisibilityQuery.filter_queryset_for_square(
                qs,
                viewer=viewer,
                kind=kind,
            )

            # ---------------------------------------------
            # 7) Boundary visibility
            # ---------------------------------------------
            qs = BoundaryVisibilityQuery.exclude_boundary_conflicts(
                qs,
                viewer=viewer,
            )

            # ---------------------------------------------
            # 8) Exclude viewer-owned content
            # ---------------------------------------------
            qs = exclude_owned_by_viewer(
                qs,
                viewer,
            )

            # ---------------------------------------------
            # 9) Relationship affinity
            # ---------------------------------------------
            if friend_owner_q is not None:
                friend_affinity = models.Case(
                    models.When(
                        friend_owner_q,
                        then=models.Value(True),
                    ),
                    default=models.Value(False),
                    output_field=models.BooleanField(),
                )
            else:
                friend_affinity = models.Value(
                    False,
                    output_field=models.BooleanField(),
                )

            # ---------------------------------------------
            # 10) Square metadata
            # ---------------------------------------------
            qs = qs.annotate(
                square_kind=models.Value(
                    source.kind,
                    output_field=models.CharField(),
                ),
                square_ct=models.Value(
                    ContentType.objects.get_for_model(
                        model
                    ).id,
                    output_field=models.IntegerField(),
                ),
                **{
                    SQUARE_FRIEND_AFFINITY_FIELD:
                        friend_affinity,
                },
            )

            querysets.append(qs)

        return querysets

    @staticmethod
    def _organization_updates(source, *, viewer=None):
        """Discover only published, public organization media updates.

        OrganizationUpdate owns no GenericForeignKey owner or is_converted
        flag. Shared ranking gets compatible annotations, but operator
        privacy and the operator's identity never become post ownership.
        """
        from apps.organization_content.models import OrganizationUpdateMedia
        from apps.organization_media.models import OrganizationMediaAsset
        from apps.organizations.constants import OrganizationVisibility, OrganizationStatus
        from apps.core.visibility.constants import VISIBILITY_GLOBAL

        uses = OrganizationUpdateMedia.objects.filter(update_id=OuterRef("pk"))
        ready = uses.filter(
            asset__status=OrganizationMediaAsset.Status.READY,
            asset__is_converted=True,
        ).filter(
            Q(asset__kind=OrganizationMediaAsset.Kind.IMAGE,
              asset__image_safety_verified=True)
            | Q(asset__kind=OrganizationMediaAsset.Kind.VIDEO)
        )
        unready = uses.exclude(
            asset__status=OrganizationMediaAsset.Status.READY,
            asset__is_converted=True,
        ) | uses.filter(
            asset__kind=OrganizationMediaAsset.Kind.IMAGE,
            asset__image_safety_verified=False,
        )

        queryset = (
            source.model.objects.select_related("organization")
            .prefetch_related("media_items__asset")
            .filter(
                status=source.model.Status.PUBLISHED,
                caption_safety_verified=True,
                is_active=True,
                is_suspended=False,
                published_at__lte=timezone.now(),
                organization__status=OrganizationStatus.ACTIVE,
                organization__visibility=OrganizationVisibility.PUBLIC,
            )
            .annotate(_square_has_media=Exists(uses),
                      _square_has_ready_media=Exists(ready),
                      _square_has_unready_media=Exists(unready))
            .filter(_square_has_media=True,
                    _square_has_ready_media=True,
                    _square_has_unready_media=False)
            .annotate(
                visibility=Value(VISIBILITY_GLOBAL, output_field=CharField()),
                object_id=Value(0, output_field=IntegerField()),
                square_kind=Value(source.kind, output_field=CharField()),
                square_is_friend_owner=Value(False, output_field=BooleanField()),
            )
        )

        if viewer is not None and getattr(viewer, "is_authenticated", False):
            # Match the existing Boundary policy for organization GFK owners.
            from apps.organizations.selectors.ownership import (
                effective_organization_owner_memberships_queryset,
            )
            conflicting_owner = (
                effective_organization_owner_memberships_queryset()
                .filter(organization_id=OuterRef("organization_id"),
                        member__is_active=True)
                .filter(Exists(
                    BoundaryVisibilityQuery._boundary_exists_for_user_id(
                        viewer=viewer,
                        user_id_outer_ref=OuterRef("member__user_id"),
                    )
                ))
            )
            queryset = queryset.exclude(Exists(conflicting_owner))

        return queryset
