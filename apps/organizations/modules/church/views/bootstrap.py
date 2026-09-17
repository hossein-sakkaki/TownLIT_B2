# apps/organizations/modules/church/views/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.modules.church.api_contract import CHURCH_API_CONTRACT_VERSION
from apps.organizations.modules.church.constants import (
    ChurchCampusStatus,
    ChurchGatheringOccurrenceStatus,
    ChurchLeadershipAssignmentStatus,
    ChurchMinistryStatus,
)
from apps.organizations.modules.church.models import ChurchCampus
from apps.organizations.modules.church.serializers import ChurchBootstrapSerializer
from apps.organizations.permissions import OrganizationsEnabledPermission

from .helpers import (
    church_access_payload,
    church_permission_map,
    get_church_request_context,
    visible_church_gatherings,
    visible_church_leadership,
    visible_church_ministries,
)


class ChurchBootstrapView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, module_access = get_church_request_context(
            user=request.user,
            slug=slug,
        )

        permissions = church_permission_map(
            user=request.user,
            workspace=workspace,
        )

        campuses = (
            ChurchCampus.objects
            .filter(
                workspace=workspace,
                status=ChurchCampusStatus.ACTIVE,
            )
            .select_related("address")
            .order_by("sort_order", "name", "id")
        )

        ministries = visible_church_ministries(
            user=request.user,
            workspace=workspace,
        ).filter(status=ChurchMinistryStatus.ACTIVE)

        leadership = visible_church_leadership(
            user=request.user,
            workspace=workspace,
        ).filter(status=ChurchLeadershipAssignmentStatus.ACTIVE)

        upcoming_gatherings = visible_church_gatherings(
            user=request.user,
            workspace=workspace,
        ).filter(
            status=ChurchGatheringOccurrenceStatus.SCHEDULED,
            ends_at__gt=timezone.now(),
        )[:50]

        payload = {
            "contract_version": CHURCH_API_CONTRACT_VERSION,
            "workspace": workspace,
            "access": church_access_payload(
                module_access=module_access,
                permissions=permissions,
            ),
            "permissions": permissions,
            "campuses": campuses,
            "ministries": ministries,
            "leadership": leadership,
            "upcoming_gatherings": upcoming_gatherings,
        }

        return Response(
            ChurchBootstrapSerializer(
                payload,
                context={"request": request},
            ).data
        )
