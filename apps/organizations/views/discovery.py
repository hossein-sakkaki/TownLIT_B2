# apps/organizations/views/discovery.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.organizations.permissions import (
    OrganizationsEnabledPermission,
)
from apps.organizations.selectors.discovery import (
    OrganizationDiscoveryFilters,
    OrganizationDiscoveryRankingPolicyV1,
    OrganizationDiscoveryService,
)
from apps.organizations.serializers.discovery import (
    OrganizationDiscoveryQuerySerializer,
    OrganizationDiscoveryResultSerializer,
)


ORGANIZATION_DISCOVERY_PAGE_SIZE = 20


class OrganizationDiscoveryPagination(
    PageNumberPagination
):
    page_size = ORGANIZATION_DISCOVERY_PAGE_SIZE
    page_size_query_param = None
    max_page_size = ORGANIZATION_DISCOVERY_PAGE_SIZE


class OrganizationDiscoveryView(APIView):
    """
    Search and filter active public TownLIT Organizations.

    The response contract is intentionally Organization-owned so Square/Explore
    and future discovery surfaces can share it without coupling Organization
    identity to Square content projections.
    """

    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]

    def get(self, request):
        query_serializer = OrganizationDiscoveryQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        filters = OrganizationDiscoveryFilters(
            kind=data.get("kind"),
            country=data.get("country"),
            city=data.get("city"),
            service_delivery_mode=data.get(
                "service_delivery_mode"
            ),
            verified=data.get("verified"),
        )

        organizations = OrganizationDiscoveryService.search(
            query=data.get("q", ""),
            filters=filters,
        )

        paginator = OrganizationDiscoveryPagination()
        page = paginator.paginate_queryset(
            organizations,
            request,
            view=self,
        )

        serializer = OrganizationDiscoveryResultSerializer(
            page,
            many=True,
            context={"request": request},
        )

        response = paginator.get_paginated_response(
            serializer.data
        )
        response[
            "X-TownLIT-Discovery-Ranking"
        ] = OrganizationDiscoveryRankingPolicyV1.version
        return response
