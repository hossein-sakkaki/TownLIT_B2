# apps/organizations/views/community.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-05.
# Last Update by Hossein Sakkaki on 2026-10-05.
#

from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.selectors.community import (
    ORGANIZATION_COMMUNITY_AUDIENCES,
    visible_organization_community_users,
)

from .access import get_visible_organization_or_404


class OrganizationCommunityPagination(
    PageNumberPagination
):
    page_size = 30
    page_size_query_param = None
    max_page_size = 30


class OrganizationCommunityPeopleView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]

    def get(self, request, slug):
        organization = (
            get_visible_organization_or_404(
                user=request.user,
                slug=slug,
            )
        )

        audience = str(
            request.query_params.get(
                "kind",
                "",
            )
            or ""
        ).strip().lower()

        if audience not in ORGANIZATION_COMMUNITY_AUDIENCES:
            raise ValidationError({
                "kind": (
                    "kind must be either "
                    "'members' or 'followers'."
                )
            })

        queryset = (
            visible_organization_community_users(
                organization=organization,
                viewer=request.user,
                audience=audience,
            )
        )

        paginator = OrganizationCommunityPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        serializer = UserMiniSerializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        return paginator.get_paginated_response(
            serializer.data
        )
