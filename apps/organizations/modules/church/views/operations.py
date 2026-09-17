# apps/organizations/modules/church/views/operations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.modules.church.constants import (
    ChurchPermissionKey,
    ChurchServicePlanStatus,
    ChurchServingAssignmentStatus,
    ChurchServingTeamStatus,
)
from apps.organizations.modules.church.models import (
    ChurchServicePlan,
    ChurchServingAssignment,
    ChurchServingTeam,
    ChurchServingTeamMembership,
)
from apps.organizations.modules.church.serializers import (
    ChurchServicePlanCreateSerializer,
    ChurchServicePlanItemCreateSerializer,
    ChurchServicePlanItemSerializer,
    ChurchServicePlanItemUpdateSerializer,
    ChurchServicePlanReferenceSerializer,
    ChurchServicePlanSerializer,
    ChurchServicePlanUpdateSerializer,
    ChurchServingAssignmentCreateSerializer,
    ChurchServingAssignmentRespondSerializer,
    ChurchServingAssignmentSerializer,
    ChurchServingTeamCreateSerializer,
    ChurchServingTeamMemberAddSerializer,
    ChurchServingTeamMembershipSerializer,
    ChurchServingTeamSerializer,
    ChurchServingTeamUpdateSerializer,
)
from apps.organizations.modules.church.services.access import (
    ensure_church_permission,
    user_has_church_permission,
)
from apps.organizations.modules.church.services.service_plans import (
    add_church_service_plan_item,
    cancel_church_service_plan,
    complete_church_service_plan,
    create_church_service_plan,
    publish_church_service_plan,
    remove_church_service_plan_item,
    update_church_service_plan,
    update_church_service_plan_item,
)
from apps.organizations.modules.church.services.serving_assignments import (
    cancel_church_serving_assignment,
    check_in_church_serving_assignment,
    check_out_church_serving_assignment,
    complete_church_serving_assignment,
    create_church_serving_assignment,
    respond_to_church_serving_assignment,
)
from apps.organizations.modules.church.services.serving_teams import (
    add_church_serving_team_member,
    create_church_serving_team,
    remove_church_serving_team_member,
    update_church_serving_team,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    ensure_any_church_permission,
    get_church_campus_or_404,
    get_church_gathering_or_404,
    get_church_ministry_or_404,
    get_church_request_context,
    get_church_service_plan_item_or_404,
    get_church_service_plan_or_404,
    get_church_serving_assignment_or_404,
    get_church_serving_team_membership_or_404,
    get_church_serving_team_or_404,
    get_organization_membership_or_404,
)


def _serialize(serializer_class, instance, request):
    return serializer_class(
        instance,
        context={"request": request},
    ).data


def _resolve_optional_campus(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_campus_or_404(
        workspace=workspace,
        public_id=public_id,
    )


def _resolve_optional_ministry(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_ministry_or_404(
        workspace=workspace,
        public_id=public_id,
    )


def _resolve_optional_team(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_serving_team_or_404(
        workspace=workspace,
        public_id=public_id,
    )


def _ensure_assignment_visible(*, user, workspace, assignment):
    if assignment.membership.member.user_id == user.id:
        return

    if user_has_church_permission(
        user=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    ):
        return

    raise NotFound("Church serving assignment not found.")


class ChurchServingTeamsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_any_church_permission(
            user=request.user,
            workspace=workspace,
            permission_keys=(
                ChurchPermissionKey.MANAGE_SERVING_TEAMS,
                ChurchPermissionKey.MANAGE_SERVICE_PLANS,
                ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
            ),
        )

        queryset = (
            ChurchServingTeam.objects
            .filter(workspace=workspace)
            .select_related("campus", "ministry")
            .order_by("sort_order", "name", "id")
        )

        if not user_has_church_permission(
            user=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
        ):
            queryset = queryset.filter(
                status=ChurchServingTeamStatus.ACTIVE,
            )

        return Response(
            ChurchServingTeamSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchServingTeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        campus = _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        )
        ministry = _resolve_optional_ministry(
            workspace=workspace,
            public_id=data.pop("ministry_public_id", None),
        )

        try:
            team = create_church_serving_team(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchServingTeamSerializer, team, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchServingTeamDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_any_church_permission(
            user=request.user,
            workspace=workspace,
            permission_keys=(
                ChurchPermissionKey.MANAGE_SERVING_TEAMS,
                ChurchPermissionKey.MANAGE_SERVICE_PLANS,
                ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
            ),
        )
        team = get_church_serving_team_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        if (
            team.status != ChurchServingTeamStatus.ACTIVE
            and not user_has_church_permission(
                user=request.user,
                workspace=workspace,
                permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
            )
        ):
            raise NotFound("Church serving team not found.")

        return Response(_serialize(ChurchServingTeamSerializer, team, request))

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        team = get_church_serving_team_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchServingTeamUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "campus_public_id" in data:
            data["campus"] = _resolve_optional_campus(
                workspace=workspace,
                public_id=data.pop("campus_public_id"),
            )
        if "ministry_public_id" in data:
            data["ministry"] = _resolve_optional_ministry(
                workspace=workspace,
                public_id=data.pop("ministry_public_id"),
            )

        try:
            team = update_church_serving_team(
                team=team,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchServingTeamSerializer, team, request))


class ChurchServingTeamMembersView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_church_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_SERVING_TEAMS,
            require_write=False,
        )
        team = get_church_serving_team_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        queryset = (
            ChurchServingTeamMembership.objects
            .filter(team=team)
            .select_related("membership__member__user")
            .order_by("-is_team_lead", "joined_at", "id")
        )
        return Response(
            ChurchServingTeamMembershipSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug, public_id):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        team = get_church_serving_team_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchServingTeamMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        membership = get_organization_membership_or_404(
            organization=organization,
            public_id=data.pop("membership_public_id"),
        )

        try:
            team_membership = add_church_serving_team_member(
                team=team,
                membership=membership,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchServingTeamMembershipSerializer,
                team_membership,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )


class ChurchServingTeamMembershipRemoveView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        team_membership = get_church_serving_team_membership_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            team_membership = remove_church_serving_team_member(
                team_membership=team_membership,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(
                ChurchServingTeamMembershipSerializer,
                team_membership,
                request,
            )
        )


class ChurchServicePlanReferencesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_any_church_permission(
            user=request.user,
            workspace=workspace,
            permission_keys=(
                ChurchPermissionKey.MANAGE_SERVICE_PLANS,
                ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
            ),
        )

        queryset = (
            ChurchServicePlan.objects
            .filter(workspace=workspace)
            .select_related("occurrence")
            .order_by("occurrence__starts_at", "id")
        )
        include_closed = request.query_params.get("include_closed") == "1"
        if not include_closed:
            queryset = queryset.exclude(
                status__in={
                    ChurchServicePlanStatus.COMPLETED,
                    ChurchServicePlanStatus.CANCELED,
                }
            )

        return Response(
            ChurchServicePlanReferenceSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )


class ChurchServicePlansView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_church_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
            require_write=False,
        )

        queryset = (
            ChurchServicePlan.objects
            .filter(workspace=workspace)
            .select_related("occurrence")
            .prefetch_related("items")
            .order_by("occurrence__starts_at", "id")
        )
        include_closed = request.query_params.get("include_closed") == "1"
        if not include_closed:
            queryset = queryset.exclude(
                status__in={
                    ChurchServicePlanStatus.COMPLETED,
                    ChurchServicePlanStatus.CANCELED,
                }
            )

        return Response(
            ChurchServicePlanSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchServicePlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        occurrence = get_church_gathering_or_404(
            workspace=workspace,
            public_id=data.pop("occurrence_public_id"),
        )

        try:
            plan = create_church_service_plan(
                occurrence=occurrence,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchServicePlanSerializer, plan, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchServicePlanDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_church_permission(
            actor=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
            require_write=False,
        )
        plan = get_church_service_plan_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        return Response(_serialize(ChurchServicePlanSerializer, plan, request))

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        plan = get_church_service_plan_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchServicePlanUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            plan = update_church_service_plan(
                plan=plan,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchServicePlanSerializer, plan, request))


class ChurchServicePlanItemsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        plan = get_church_service_plan_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchServicePlanItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        team = _resolve_optional_team(
            workspace=workspace,
            public_id=data.pop("serving_team_public_id", None),
        )
        ministry = _resolve_optional_ministry(
            workspace=workspace,
            public_id=data.pop("ministry_public_id", None),
        )

        try:
            item = add_church_service_plan_item(
                plan=plan,
                actor=request.user,
                serving_team=team,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchServicePlanItemSerializer, item, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchServicePlanItemDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        item = get_church_service_plan_item_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchServicePlanItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if "serving_team_public_id" in data:
            data["serving_team"] = _resolve_optional_team(
                workspace=workspace,
                public_id=data.pop("serving_team_public_id"),
            )
        if "ministry_public_id" in data:
            data["ministry"] = _resolve_optional_ministry(
                workspace=workspace,
                public_id=data.pop("ministry_public_id"),
            )

        try:
            item = update_church_service_plan_item(
                item=item,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchServicePlanItemSerializer, item, request))

    def delete(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        item = get_church_service_plan_item_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            remove_church_service_plan_item(
                item=item,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)


class _ChurchServicePlanLifecycleView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]
    action = None

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        plan = get_church_service_plan_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            plan = self.action(plan=plan, actor=request.user)
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchServicePlanSerializer, plan, request))


class ChurchServicePlanPublishView(_ChurchServicePlanLifecycleView):
    action = staticmethod(publish_church_service_plan)


class ChurchServicePlanCompleteView(_ChurchServicePlanLifecycleView):
    action = staticmethod(complete_church_service_plan)


class ChurchServicePlanCancelView(_ChurchServicePlanLifecycleView):
    action = staticmethod(cancel_church_service_plan)


class ChurchServingAssignmentsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        can_manage = user_has_church_permission(
            user=request.user,
            workspace=workspace,
            permission_key=ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
        )

        queryset = (
            ChurchServingAssignment.objects
            .filter(service_plan__workspace=workspace)
            .select_related(
                "service_plan__occurrence",
                "membership__member__user",
                "team",
            )
            .order_by("service_plan__occurrence__starts_at", "id")
        )

        if not can_manage:
            queryset = queryset.filter(
                membership__member__user=request.user,
            )

        include_closed = request.query_params.get("include_closed") == "1"
        if not include_closed:
            queryset = queryset.exclude(
                status__in={
                    ChurchServingAssignmentStatus.CANCELED,
                    ChurchServingAssignmentStatus.COMPLETED,
                }
            )

        return Response(
            ChurchServingAssignmentSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        serializer = ChurchServingAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        service_plan = get_church_service_plan_or_404(
            workspace=workspace,
            public_id=data.pop("service_plan_public_id"),
        )
        membership = get_organization_membership_or_404(
            organization=organization,
            public_id=data.pop("membership_public_id"),
        )
        team = _resolve_optional_team(
            workspace=workspace,
            public_id=data.pop("team_public_id", None),
        )

        try:
            assignment = create_church_serving_assignment(
                service_plan=service_plan,
                membership=membership,
                actor=request.user,
                team=team,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchServingAssignmentSerializer, assignment, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchServingAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        assignment = get_church_serving_assignment_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        _ensure_assignment_visible(
            user=request.user,
            workspace=workspace,
            assignment=assignment,
        )
        return Response(
            _serialize(ChurchServingAssignmentSerializer, assignment, request)
        )


class ChurchServingAssignmentRespondView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        assignment = get_church_serving_assignment_or_404(
            workspace=workspace,
            public_id=public_id,
        )
        serializer = ChurchServingAssignmentRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = respond_to_church_serving_assignment(
                assignment=assignment,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchServingAssignmentSerializer, assignment, request)
        )


class _ChurchServingAssignmentActionView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]
    action = None

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        assignment = get_church_serving_assignment_or_404(
            workspace=workspace,
            public_id=public_id,
        )

        try:
            assignment = self.action(
                assignment=assignment,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchServingAssignmentSerializer, assignment, request)
        )


class ChurchServingAssignmentCheckInView(_ChurchServingAssignmentActionView):
    action = staticmethod(check_in_church_serving_assignment)


class ChurchServingAssignmentCheckOutView(_ChurchServingAssignmentActionView):
    action = staticmethod(check_out_church_serving_assignment)


class ChurchServingAssignmentCancelView(_ChurchServingAssignmentActionView):
    action = staticmethod(cancel_church_serving_assignment)


class ChurchServingAssignmentCompleteView(_ChurchServingAssignmentActionView):
    action = staticmethod(complete_church_serving_assignment)
