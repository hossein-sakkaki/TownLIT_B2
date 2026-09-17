# apps/organizations/modules/church/views/helpers.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.apps import apps
from django.db.models import Q

from rest_framework.exceptions import NotFound, PermissionDenied

from apps.organizations.constants import (
    OrganizationMembershipStatus,
    OrganizationModuleAccessMode,
    OrganizationModuleKey,
    OrganizationModuleVisibility,
)
from apps.organizations.models import OrganizationMembership
from apps.organizations.modules.church.constants import ChurchPermissionKey
from apps.organizations.modules.church.models import (
    ChurchAttendanceRecord,
    ChurchAttendanceSession,
    ChurchCampus,
    ChurchCongregant,
    ChurchHousehold,
    ChurchHouseholdMembership,
    ChurchGatheringOccurrence,
    ChurchGatheringSeries,
    ChurchLeadershipAssignment,
    ChurchMinistry,
    ChurchResource,
    ChurchResourceReservation,
    ChurchServicePlan,
    ChurchServicePlanItem,
    ChurchServingAssignment,
    ChurchServingTeam,
    ChurchServingTeamMembership,
)
from apps.organizations.modules.church.selectors.church import get_church_workspace
from apps.organizations.modules.church.services.access import (
    ensure_church_module_access,
    user_has_church_permission,
)
from apps.organizations.modules.church.services.pastoral_access import (
    user_has_direct_church_permission,
)
from apps.organizations.services.modules import get_organization_module_access
from apps.organizations.views.access import get_visible_organization_or_404


PASTORAL_PERMISSION_KEYS = {
    ChurchPermissionKey.VIEW_PASTORAL_CARE,
    ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
}

CHURCH_PERMISSION_KEYS = (
    ChurchPermissionKey.MANAGE_WORKSPACE,
    ChurchPermissionKey.MANAGE_CAMPUSES,
    ChurchPermissionKey.MANAGE_MINISTRIES,
    ChurchPermissionKey.MANAGE_LEADERSHIP,
    ChurchPermissionKey.MANAGE_GATHERINGS,
    ChurchPermissionKey.VIEW_ATTENDANCE,
    ChurchPermissionKey.MANAGE_ATTENDANCE,
    ChurchPermissionKey.MANAGE_SERVING_TEAMS,
    ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    ChurchPermissionKey.MANAGE_RESOURCES,
    ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
    ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    ChurchPermissionKey.MANAGE_HOUSEHOLDS,
    ChurchPermissionKey.VIEW_PASTORAL_CARE,
    ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
    ChurchPermissionKey.VIEW_TEACHING,
    ChurchPermissionKey.MANAGE_TEACHING,
    ChurchPermissionKey.PUBLISH_TEACHING,
)

CHURCH_WRITE_PERMISSION_KEYS = {
    ChurchPermissionKey.MANAGE_WORKSPACE,
    ChurchPermissionKey.MANAGE_CAMPUSES,
    ChurchPermissionKey.MANAGE_MINISTRIES,
    ChurchPermissionKey.MANAGE_LEADERSHIP,
    ChurchPermissionKey.MANAGE_GATHERINGS,
    ChurchPermissionKey.MANAGE_ATTENDANCE,
    ChurchPermissionKey.MANAGE_SERVING_TEAMS,
    ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    ChurchPermissionKey.MANAGE_RESOURCES,
    ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    ChurchPermissionKey.MANAGE_HOUSEHOLDS,
    ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    ChurchPermissionKey.MANAGE_TEACHING,
    ChurchPermissionKey.PUBLISH_TEACHING,
}


def get_church_request_context(*, user, slug):
    organization = get_visible_organization_or_404(
        user=user,
        slug=slug,
    )
    workspace = get_church_workspace(organization=organization)

    if not workspace:
        raise NotFound("Church workspace not found.")

    ensure_church_module_access(
        workspace=workspace,
        require_write=False,
    )

    module_access = get_organization_module_access(
        organization=organization,
        module_key=OrganizationModuleKey.CHURCH,
        actor=user,
    )

    return organization, workspace, module_access


def church_permission_map(*, user, workspace):
    result = {}

    for permission_key in CHURCH_PERMISSION_KEYS:
        if permission_key in PASTORAL_PERMISSION_KEYS:
            allowed = user_has_direct_church_permission(
                user=user,
                workspace=workspace,
                permission_key=permission_key,
            )
        else:
            allowed = user_has_church_permission(
                user=user,
                workspace=workspace,
                permission_key=permission_key,
            )

        result[permission_key] = bool(allowed)

    return result


def church_access_payload(*, module_access, permissions):
    return {
        "access_mode": module_access.access_mode,
        "reason": module_access.reason,
        "is_verified": bool(module_access.is_verified),
        "has_entitlement": bool(module_access.has_entitlement),
        "can_manage_module": bool(module_access.can_manage),
        "domain_writable": bool(
            module_access.access_mode == OrganizationModuleAccessMode.FULL
            and any(
                permissions.get(permission_key, False)
                for permission_key in CHURCH_WRITE_PERMISSION_KEYS
            )
        ),
    }


def viewer_is_active_organization_member(*, user, organization) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    return OrganizationMembership.objects.filter(
        organization=organization,
        member__user=user,
        status=OrganizationMembershipStatus.ACTIVE,
    ).exists()


def _visibility_filter(*, user, workspace, manage_permission_key):
    if user_has_church_permission(
        user=user,
        workspace=workspace,
        permission_key=manage_permission_key,
    ):
        return Q()

    if viewer_is_active_organization_member(
        user=user,
        organization=workspace.activation.organization,
    ):
        return Q(
            visibility__in={
                OrganizationModuleVisibility.PUBLIC,
                OrganizationModuleVisibility.MEMBERS_ONLY,
            }
        )

    return Q(visibility=OrganizationModuleVisibility.PUBLIC)


def visible_church_ministries(*, user, workspace):
    return (
        ChurchMinistry.objects
        .filter(workspace=workspace)
        .filter(
            _visibility_filter(
                user=user,
                workspace=workspace,
                manage_permission_key=ChurchPermissionKey.MANAGE_MINISTRIES,
            )
        )
        .select_related("campus")
        .order_by("sort_order", "name", "id")
    )


def visible_church_leadership(*, user, workspace):
    queryset = (
        ChurchLeadershipAssignment.objects
        .filter(workspace=workspace)
        .select_related(
            "membership__member__user",
            "campus",
            "ministry",
        )
        .order_by("sort_order", "position_type", "id")
    )

    if user_has_church_permission(
        user=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_LEADERSHIP,
    ):
        return queryset

    return queryset.filter(publicly_listed=True)


def visible_church_gathering_series(*, user, workspace):
    return (
        ChurchGatheringSeries.objects
        .filter(workspace=workspace)
        .filter(
            _visibility_filter(
                user=user,
                workspace=workspace,
                manage_permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
            )
        )
        .select_related("campus", "ministry")
        .order_by("name", "id")
    )


def visible_church_gatherings(*, user, workspace):
    return (
        ChurchGatheringOccurrence.objects
        .filter(workspace=workspace)
        .filter(
            _visibility_filter(
                user=user,
                workspace=workspace,
                manage_permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
            )
        )
        .select_related("campus", "ministry", "series")
        .order_by("starts_at", "id")
    )


def get_church_campus_or_404(*, workspace, public_id):
    campus = (
        ChurchCampus.objects
        .select_related("workspace__activation__organization", "address")
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not campus:
        raise NotFound("Church campus not found.")
    return campus


def get_church_ministry_or_404(*, workspace, public_id):
    ministry = (
        ChurchMinistry.objects
        .select_related("workspace__activation__organization", "campus")
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not ministry:
        raise NotFound("Church ministry not found.")
    return ministry


def get_church_leadership_or_404(*, workspace, public_id):
    assignment = (
        ChurchLeadershipAssignment.objects
        .select_related(
            "workspace__activation__organization",
            "membership__member__user",
            "campus",
            "ministry",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not assignment:
        raise NotFound("Church leadership assignment not found.")
    return assignment


def get_church_gathering_series_or_404(*, workspace, public_id):
    series = (
        ChurchGatheringSeries.objects
        .select_related(
            "workspace__activation__organization",
            "campus",
            "ministry",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not series:
        raise NotFound("Church gathering series not found.")
    return series


def get_church_gathering_or_404(*, workspace, public_id):
    occurrence = (
        ChurchGatheringOccurrence.objects
        .select_related(
            "workspace__activation__organization",
            "series",
            "campus",
            "ministry",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not occurrence:
        raise NotFound("Church gathering not found.")
    return occurrence


def get_organization_membership_or_404(*, organization, public_id):
    membership = (
        OrganizationMembership.objects
        .select_related("member__user", "organization")
        .filter(
            organization=organization,
            public_id=public_id,
        )
        .first()
    )
    if not membership:
        raise NotFound("Organization membership not found.")
    return membership


def get_address_or_404(address_id):
    if address_id is None:
        return None

    Address = apps.get_model("accounts", "Address")
    address = Address.objects.filter(pk=address_id).first()
    if not address:
        raise NotFound("Address not found.")
    return address



def ensure_any_church_permission(*, user, workspace, permission_keys):
    ensure_church_module_access(
        workspace=workspace,
        require_write=False,
    )

    for permission_key in permission_keys:
        if user_has_church_permission(
            user=user,
            workspace=workspace,
            permission_key=permission_key,
        ):
            return

    raise PermissionDenied(
        "You do not have permission to access this Church operation."
    )


def get_church_attendance_session_or_404(*, workspace, public_id):
    session = (
        ChurchAttendanceSession.objects
        .select_related(
            "workspace__activation__organization",
            "occurrence",
        )
        .prefetch_related("records__membership__member__user")
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not session:
        raise NotFound("Church attendance session not found.")
    return session


def get_church_attendance_record_or_404(*, workspace, public_id):
    record = (
        ChurchAttendanceRecord.objects
        .select_related(
            "session__workspace__activation__organization",
            "membership__member__user",
        )
        .filter(
            session__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not record:
        raise NotFound("Church attendance record not found.")
    return record


def get_church_serving_team_or_404(*, workspace, public_id):
    team = (
        ChurchServingTeam.objects
        .select_related(
            "workspace__activation__organization",
            "campus",
            "ministry",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not team:
        raise NotFound("Church serving team not found.")
    return team


def get_church_serving_team_membership_or_404(*, workspace, public_id):
    membership = (
        ChurchServingTeamMembership.objects
        .select_related(
            "team__workspace__activation__organization",
            "membership__member__user",
        )
        .filter(
            team__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not membership:
        raise NotFound("Church serving team membership not found.")
    return membership


def get_church_service_plan_or_404(*, workspace, public_id):
    plan = (
        ChurchServicePlan.objects
        .select_related(
            "workspace__activation__organization",
            "occurrence",
        )
        .prefetch_related("items", "serving_assignments")
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not plan:
        raise NotFound("Church service plan not found.")
    return plan


def get_church_service_plan_item_or_404(*, workspace, public_id):
    item = (
        ChurchServicePlanItem.objects
        .select_related(
            "service_plan__workspace__activation__organization",
            "serving_team",
            "ministry",
        )
        .filter(
            service_plan__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not item:
        raise NotFound("Church service plan item not found.")
    return item


def get_church_serving_assignment_or_404(*, workspace, public_id):
    assignment = (
        ChurchServingAssignment.objects
        .select_related(
            "service_plan__workspace__activation__organization",
            "service_plan__occurrence",
            "membership__member__user",
            "team",
        )
        .filter(
            service_plan__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not assignment:
        raise NotFound("Church serving assignment not found.")
    return assignment


def get_church_resource_or_404(*, workspace, public_id):
    resource = (
        ChurchResource.objects
        .select_related(
            "workspace__activation__organization",
            "campus",
            "ministry",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not resource:
        raise NotFound("Church resource not found.")
    return resource


def get_church_resource_reservation_or_404(*, workspace, public_id):
    reservation = (
        ChurchResourceReservation.objects
        .select_related(
            "resource__workspace__activation__organization",
            "occurrence",
        )
        .filter(
            resource__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not reservation:
        raise NotFound("Church resource reservation not found.")
    return reservation


def get_church_congregant_or_404(*, workspace, public_id):
    congregant = (
        ChurchCongregant.objects
        .select_related(
            "workspace__activation__organization",
            "member__user",
            "guest_profile__user",
            "official_membership",
            "campus",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not congregant:
        raise NotFound("Church congregant not found.")
    return congregant


def get_church_household_or_404(*, workspace, public_id):
    household = (
        ChurchHousehold.objects
        .select_related("workspace", "campus")
        .prefetch_related(
            "memberships__congregant__member__user",
            "memberships__congregant__guest_profile__user",
            "memberships__congregant__campus",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not household:
        raise NotFound("Church household not found.")
    return household


def get_church_household_membership_or_404(*, workspace, public_id):
    membership = (
        ChurchHouseholdMembership.objects
        .select_related(
            "household__workspace",
            "congregant__member__user",
            "congregant__guest_profile__user",
            "congregant__campus",
        )
        .filter(
            household__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not membership:
        raise NotFound("Church household membership not found.")
    return membership
