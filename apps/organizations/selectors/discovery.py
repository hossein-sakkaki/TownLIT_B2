# apps/organizations/selectors/discovery.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata

from django.db.models import (
    Case,
    IntegerField,
    Q,
    QuerySet,
    TextField,
    Value,
    When,
)
from django.db.models.functions import Cast
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationStatus,
    OrganizationVerificationGrantType,
    OrganizationVisibility,
)
from apps.organizations.models import Organization
from apps.organizations.selectors.verification import (
    active_verification_grants_queryset,
)


ORGANIZATION_DISCOVERY_MIN_QUERY_LENGTH = 2
ORGANIZATION_DISCOVERY_CANDIDATE_LIMIT = 800
ORGANIZATION_DISCOVERY_VERIFICATION_MAX_DEPTH = 8


@dataclass(frozen=True)
class OrganizationDiscoveryFilters:
    kind: str | None = None
    country: str | None = None
    city: str | None = None
    service_delivery_mode: str | None = None
    verified: bool | None = None

    @property
    def has_any_filter(self) -> bool:
        return any(
            value is not None
            for value in (
                self.kind,
                self.country,
                self.city,
                self.service_delivery_mode,
                self.verified,
            )
        )


class OrganizationDiscoveryRankingPolicyV1:
    """
    Server-owned Organization discovery ranking policy.

    Stable contract:
    - verified Organizations are promoted first;
    - textual relevance decides the next ordering layer;
    - profile completeness provides a quality tie-break;
    - recency and stable identity make ordering deterministic.

    The API intentionally does not expose raw scores. Future ranking signals can
    evolve behind this policy without changing the discovery response shape.
    """

    version = "organization.discovery.v1"

    FIELD_WEIGHTS = (
        ("name", 120),
        ("short_name", 112),
        ("slug", 104),
        ("activity_areas", 92),
        ("tagline", 80),
        ("kind", 62),
        ("city", 56),
        ("province_region", 50),
        ("country", 44),
        ("service_delivery_mode", 38),
        ("description", 24),
    )

    @classmethod
    def sort_key(
        cls,
        organization: Organization,
        *,
        normalized_query: str,
        is_verified: bool,
    ) -> tuple:
        relevance = cls.text_relevance(
            organization,
            normalized_query=normalized_query,
        )
        quality = cls.profile_quality(organization)
        updated_at = getattr(organization, "updated_at", None)
        updated_timestamp = cls._timestamp(updated_at)

        return (
            0 if is_verified else 1,
            -relevance,
            -quality,
            -updated_timestamp,
            cls._normalize(getattr(organization, "name", "")),
            int(getattr(organization, "id", 0) or 0),
        )

    @classmethod
    def text_relevance(
        cls,
        organization: Organization,
        *,
        normalized_query: str,
    ) -> int:
        if not normalized_query:
            return 0

        tokens = cls._tokens(normalized_query)
        score = 0

        for field_name, weight in cls.FIELD_WEIGHTS:
            values = cls._field_values(
                organization,
                field_name,
            )

            for value in values:
                normalized_value = cls._normalize(value)
                if not normalized_value:
                    continue

                if normalized_value == normalized_query:
                    score += weight * 8
                elif normalized_value.startswith(normalized_query):
                    score += weight * 5
                elif normalized_query in normalized_value:
                    score += weight * 3

                for token in tokens:
                    if normalized_value == token:
                        score += weight * 4
                    elif normalized_value.startswith(token):
                        score += weight * 2
                    elif token in normalized_value:
                        score += weight

        return score

    @staticmethod
    def profile_quality(
        organization: Organization,
    ) -> int:
        score = 0

        if getattr(organization, "logo", None):
            score += 24
        if getattr(organization, "thumbnail", None):
            score += 8
        if str(getattr(organization, "tagline", "") or "").strip():
            score += 12
        if str(getattr(organization, "description", "") or "").strip():
            score += 14
        if getattr(organization, "activity_areas", None):
            score += 12
        if str(getattr(organization, "country", "") or "").strip():
            score += 6
        if str(getattr(organization, "city", "") or "").strip():
            score += 6
        if str(getattr(organization, "website_url", "") or "").strip():
            score += 8
        if str(getattr(organization, "brand_color", "") or "").strip():
            score += 4
        if str(getattr(organization, "service_delivery_mode", "") or "").strip():
            score += 6

        return score

    @classmethod
    def _field_values(
        cls,
        organization: Organization,
        field_name: str,
    ) -> tuple[str, ...]:
        value = getattr(organization, field_name, None)

        if isinstance(value, (list, tuple, set)):
            return tuple(
                str(item)
                for item in value
                if item is not None
            )

        if value is None:
            return ()

        return (str(value),)

    @staticmethod
    def _timestamp(value) -> float:
        if isinstance(value, datetime):
            try:
                return value.timestamp()
            except Exception:
                return 0.0
        return 0.0

    @staticmethod
    def _normalize(value: object) -> str:
        text = unicodedata.normalize(
            "NFKC",
            str(value or ""),
        )
        return " ".join(
            text.casefold().split()
        )

    @classmethod
    def _tokens(cls, value: str) -> tuple[str, ...]:
        return tuple(
            token
            for token in re.split(r"\s+", cls._normalize(value))
            if token
        )


class OrganizationDiscoveryService:
    ranking_policy = OrganizationDiscoveryRankingPolicyV1

    @classmethod
    def search(
        cls,
        *,
        query: str | None,
        filters: OrganizationDiscoveryFilters | None = None,
        now=None,
    ) -> list[Organization]:
        filters = filters or OrganizationDiscoveryFilters()
        now = now or timezone.now()
        normalized_query = cls.ranking_policy._normalize(query)

        if (
            0 < len(normalized_query) < ORGANIZATION_DISCOVERY_MIN_QUERY_LENGTH
            and not filters.has_any_filter
        ):
            return []

        if not normalized_query and not filters.has_any_filter:
            return []

        queryset = cls._base_queryset(filters=filters)

        if len(normalized_query) >= ORGANIZATION_DISCOVERY_MIN_QUERY_LENGTH:
            queryset = cls._apply_text_filter(
                queryset,
                query=normalized_query,
            )
            queryset = cls._apply_candidate_priority(
                queryset,
                query=normalized_query,
            )
        else:
            queryset = queryset.order_by(
                "-updated_at",
                "name",
                "id",
            )

        candidates = list(
            queryset[:ORGANIZATION_DISCOVERY_CANDIDATE_LIMIT]
        )

        verified_by_id = cls._resolve_verification_map(
            organization_ids={
                int(organization.id)
                for organization in candidates
            },
            now=now,
        )

        if filters.verified is not None:
            candidates = [
                organization
                for organization in candidates
                if verified_by_id.get(
                    int(organization.id),
                    False,
                )
                is filters.verified
            ]

        for organization in candidates:
            organization._discovery_is_verified = bool(
                verified_by_id.get(
                    int(organization.id),
                    False,
                )
            )

        candidates.sort(
            key=lambda organization: cls.ranking_policy.sort_key(
                organization,
                normalized_query=normalized_query,
                is_verified=bool(
                    verified_by_id.get(
                        int(organization.id),
                        False,
                    )
                ),
            )
        )

        return candidates

    @staticmethod
    def _base_queryset(
        *,
        filters: OrganizationDiscoveryFilters,
    ) -> QuerySet:
        queryset = (
            Organization.objects
            .filter(
                status=OrganizationStatus.ACTIVE,
                visibility=OrganizationVisibility.PUBLIC,
            )
            .annotate(
                _discovery_activity_text=Cast(
                    "activity_areas",
                    output_field=TextField(),
                )
            )
        )

        if filters.kind:
            queryset = queryset.filter(
                kind=filters.kind
            )

        if filters.country:
            queryset = queryset.filter(
                country__iexact=filters.country
            )

        if filters.city:
            queryset = queryset.filter(
                city__iexact=filters.city
            )

        if filters.service_delivery_mode:
            queryset = queryset.filter(
                service_delivery_mode=(
                    filters.service_delivery_mode
                )
            )

        return queryset

    @classmethod
    def _apply_text_filter(
        cls,
        queryset: QuerySet,
        *,
        query: str,
    ) -> QuerySet:
        for token in cls.ranking_policy._tokens(query):
            queryset = queryset.filter(
                cls._token_filter(token)
            )

        return queryset

    @staticmethod
    def _token_filter(token: str) -> Q:
        return (
            Q(name__icontains=token)
            | Q(short_name__icontains=token)
            | Q(slug__icontains=token)
            | Q(tagline__icontains=token)
            | Q(description__icontains=token)
            | Q(kind__icontains=token)
            | Q(city__icontains=token)
            | Q(province_region__icontains=token)
            | Q(country__icontains=token)
            | Q(service_delivery_mode__icontains=token)
            | Q(_discovery_activity_text__icontains=token)
        )

    @staticmethod
    def _apply_candidate_priority(
        queryset: QuerySet,
        *,
        query: str,
    ) -> QuerySet:
        # Cheap DB-side relevance narrows the bounded candidate pool. The
        # authoritative ranking policy still runs after verification resolution.
        return (
            queryset
            .annotate(
                _discovery_candidate_rank=Case(
                    When(
                        Q(name__iexact=query)
                        | Q(short_name__iexact=query)
                        | Q(slug__iexact=query),
                        then=Value(0),
                    ),
                    When(
                        Q(name__istartswith=query)
                        | Q(short_name__istartswith=query)
                        | Q(slug__istartswith=query),
                        then=Value(1),
                    ),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by(
                "_discovery_candidate_rank",
                "-updated_at",
                "name",
                "id",
            )
        )

    @classmethod
    def _resolve_verification_map(
        cls,
        *,
        organization_ids: set[int],
        now,
    ) -> dict[int, bool]:
        if not organization_ids:
            return {}

        grants_by_organization: dict[
            int,
            tuple[str, int | None],
        ] = {}

        frontier = set(organization_ids)
        visited: set[int] = set()

        for _ in range(
            ORGANIZATION_DISCOVERY_VERIFICATION_MAX_DEPTH
        ):
            frontier -= visited
            if not frontier:
                break

            visited.update(frontier)

            rows = (
                active_verification_grants_queryset(now=now)
                .filter(organization_id__in=frontier)
                .order_by(
                    "organization_id",
                    "-granted_at",
                    "-id",
                )
                .values(
                    "organization_id",
                    "grant_type",
                    "relationship__source_organization_id",
                )
            )

            next_frontier: set[int] = set()

            for row in rows:
                organization_id = int(
                    row["organization_id"]
                )

                if organization_id in grants_by_organization:
                    continue

                sponsor_id = row.get(
                    "relationship__source_organization_id"
                )
                sponsor_id = (
                    int(sponsor_id)
                    if sponsor_id
                    else None
                )

                grants_by_organization[organization_id] = (
                    str(row["grant_type"]),
                    sponsor_id,
                )

                if (
                    row["grant_type"]
                    == OrganizationVerificationGrantType.SPONSORED_BRANCH
                    and sponsor_id
                ):
                    next_frontier.add(sponsor_id)

            frontier = next_frontier

        memo: dict[int, bool] = {}

        def resolve(
            organization_id: int,
            stack: set[int],
        ) -> bool:
            if organization_id in memo:
                return memo[organization_id]

            if organization_id in stack:
                memo[organization_id] = False
                return False

            grant = grants_by_organization.get(
                organization_id
            )
            if not grant:
                memo[organization_id] = False
                return False

            grant_type, sponsor_id = grant

            if grant_type == OrganizationVerificationGrantType.DIRECT:
                memo[organization_id] = True
                return True

            if (
                grant_type
                != OrganizationVerificationGrantType.SPONSORED_BRANCH
                or not sponsor_id
            ):
                memo[organization_id] = False
                return False

            next_stack = set(stack)
            next_stack.add(organization_id)

            result = resolve(
                sponsor_id,
                next_stack,
            )
            memo[organization_id] = result
            return result

        return {
            organization_id: resolve(
                organization_id,
                set(),
            )
            for organization_id in organization_ids
        }
