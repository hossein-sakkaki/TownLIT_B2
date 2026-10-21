# apps/organization_content/views/bootstrap.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-10-19.

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import viewsets

from apps.organization_content.publishing_policy import upload_policy_payload

from apps.organization_content.api_contract import (
    ORGANIZATION_CONTENT_API_CONTRACT_VERSION,
)
from apps.organization_content.feature_flags import (
    organization_content_writes_enabled,
)


class OrganizationContentBootstrapViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        return Response({
            "contract_version": ORGANIZATION_CONTENT_API_CONTRACT_VERSION,
            "writes_enabled": organization_content_writes_enabled(),
            "upload_policy": upload_policy_payload(),
        })
