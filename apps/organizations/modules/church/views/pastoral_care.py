# apps/organizations/modules/church/views/pastoral_care.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import ConfigurablePagination
from apps.organizations.modules.church.constants import (
    ChurchPastoralCareAssignmentRole,
    ChurchPastoralCareAssignmentStatus,
    ChurchPastoralCareCaseStatus,
    ChurchPastoralCareCategory,
    ChurchPastoralCareContactType,
    ChurchPastoralCareNoteType,
    ChurchPastoralCareNoteVisibility,
    ChurchPastoralCareSensitivity,
)
from apps.organizations.modules.church.models import (
    ChurchPastoralCareAssignment,
    ChurchPastoralCareCase,
    ChurchPastoralCareContact,
    ChurchPastoralCareNote,
)
from apps.organizations.modules.church.selectors.pastoral_care import (
    list_pastoral_care_cases_for_actor,
    list_pastoral_care_notes_for_actor,
)
from apps.organizations.modules.church.serializers import (
    ChurchPastoralCareAssignmentCreateSerializer,
    ChurchPastoralCareAssignmentSerializer,
    ChurchPastoralCareCaseCreateSerializer,
    ChurchPastoralCareCaseListSerializer,
    ChurchPastoralCareCaseSerializer,
    ChurchPastoralCareCloseSerializer,
    ChurchPastoralCareContactCreateSerializer,
    ChurchPastoralCareContactSerializer,
    ChurchPastoralCareNoteCreateSerializer,
    ChurchPastoralCareNoteSerializer,
    ChurchPastoralCareReferenceSerializer,
)
from apps.organizations.modules.church.services.pastoral_access import (
    ensure_pastoral_manage_permission,
)
from apps.organizations.modules.church.services.pastoral_care import (
    add_pastoral_care_note,
    assign_pastoral_care_case,
    close_pastoral_care_case,
    create_pastoral_care_case,
    end_pastoral_care_assignment,
    put_pastoral_care_case_on_hold,
    record_pastoral_care_contact,
    reopen_pastoral_care_case,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error

from .helpers import (
    get_church_congregant_or_404,
    get_church_request_context,
    get_organization_membership_or_404,
)


class ChurchPastoralPagination(ConfigurablePagination):
    page_size = 50
    max_page_size = 100


def _serialize(serializer_class, instance, request, *, many=False):
    return serializer_class(
        instance,
        many=many,
        context={"request": request},
    ).data


def _paginate(*, request, view, queryset, serializer_class):
    paginator = ChurchPastoralPagination()
    page = paginator.paginate_queryset(
        queryset,
        request,
        view=view,
    )
    serializer = serializer_class(
        page,
        many=True,
        context={"request": request},
    )
    return paginator.get_paginated_response(serializer.data)


def _choice_payload(choices):
    return [
        {"value": value, "label": str(label)}
        for value, label in choices
    ]


def _get_visible_case_or_404(*, workspace, actor, public_id):
    care_case = (
        list_pastoral_care_cases_for_actor(
            workspace=workspace,
            actor=actor,
        )
        .select_related(
            "congregant__campus",
            "opened_by_membership",
            "closed_by_membership",
        )
        .prefetch_related(
            "assignments__membership__member__user",
        )
        .filter(public_id=public_id)
        .first()
    )
    if not care_case:
        raise NotFound("Pastoral care case not found.")
    return care_case


def _get_manageable_case_or_404(*, workspace, actor, public_id):
    ensure_pastoral_manage_permission(
        actor=actor,
        workspace=workspace,
        require_write=True,
    )
    care_case = (
        ChurchPastoralCareCase.objects
        .select_related(
            "workspace__activation__organization",
            "congregant__member__user",
            "congregant__guest_profile__user",
            "congregant__campus",
            "opened_by_membership",
            "closed_by_membership",
        )
        .prefetch_related(
            "assignments__membership__member__user",
        )
        .filter(
            workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not care_case:
        raise NotFound("Pastoral care case not found.")
    return care_case


def _get_manageable_assignment_or_404(*, workspace, actor, public_id):
    ensure_pastoral_manage_permission(
        actor=actor,
        workspace=workspace,
        require_write=True,
    )
    assignment = (
        ChurchPastoralCareAssignment.objects
        .select_related(
            "case__workspace__activation__organization",
            "membership__member__user",
        )
        .filter(
            case__workspace=workspace,
            public_id=public_id,
        )
        .first()
    )
    if not assignment:
        raise NotFound("Pastoral care assignment not found.")
    return assignment


def _get_visible_amended_note_or_404(*, care_case, actor, public_id):
    if public_id is None:
        return None

    note = (
        list_pastoral_care_notes_for_actor(
            care_case=care_case,
            actor=actor,
        )
        .filter(public_id=public_id)
        .first()
    )
    if not note:
        raise NotFound("Pastoral care note not found.")
    return note


def _apply_case_filters(*, queryset, request):
    query = " ".join(str(request.query_params.get("q") or "").split())
    status_value = request.query_params.get("status")
    sensitivity = request.query_params.get("sensitivity")
    category = request.query_params.get("category")
    congregant_public_id = request.query_params.get("congregant")

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(congregant__preferred_name__icontains=query)
            | Q(congregant__display_name_snapshot__icontains=query)
            | Q(congregant__member__user__username__icontains=query)
            | Q(congregant__member__user__name__icontains=query)
            | Q(congregant__member__user__family__icontains=query)
            | Q(congregant__guest_profile__user__username__icontains=query)
            | Q(congregant__guest_profile__user__name__icontains=query)
            | Q(congregant__guest_profile__user__family__icontains=query)
        )

    if status_value:
        valid = {value for value, _ in ChurchPastoralCareCaseStatus.choices}
        if status_value not in valid:
            raise ValidationError({"status": "Unsupported pastoral care case status."})
        queryset = queryset.filter(status=status_value)

    if sensitivity:
        valid = {value for value, _ in ChurchPastoralCareSensitivity.choices}
        if sensitivity not in valid:
            raise ValidationError({"sensitivity": "Unsupported pastoral care sensitivity."})
        queryset = queryset.filter(sensitivity=sensitivity)

    if category:
        valid = {value for value, _ in ChurchPastoralCareCategory.choices}
        if category not in valid:
            raise ValidationError({"category": "Unsupported pastoral care category."})
        queryset = queryset.filter(category=category)

    if congregant_public_id:
        try:
            congregant_public_id = UUID(str(congregant_public_id))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError({"congregant": "Invalid congregant public ID."})
        queryset = queryset.filter(congregant__public_id=congregant_public_id)

    return queryset


class ChurchPastoralCareReferencesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        get_church_request_context(
            user=request.user,
            slug=slug,
        )
        payload = {
            "case_statuses": _choice_payload(ChurchPastoralCareCaseStatus.choices),
            "categories": _choice_payload(ChurchPastoralCareCategory.choices),
            "sensitivities": _choice_payload(ChurchPastoralCareSensitivity.choices),
            "assignment_roles": _choice_payload(ChurchPastoralCareAssignmentRole.choices),
            "assignment_statuses": _choice_payload(ChurchPastoralCareAssignmentStatus.choices),
            "note_types": _choice_payload(ChurchPastoralCareNoteType.choices),
            "note_visibilities": _choice_payload(ChurchPastoralCareNoteVisibility.choices),
            "contact_types": _choice_payload(ChurchPastoralCareContactType.choices),
        }
        return Response(ChurchPastoralCareReferenceSerializer(payload).data)


class ChurchPastoralCareCasesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        queryset = (
            list_pastoral_care_cases_for_actor(
                workspace=workspace,
                actor=request.user,
            )
            .select_related("congregant__campus")
        )
        queryset = _apply_case_filters(
            queryset=queryset,
            request=request,
        )
        return _paginate(
            request=request,
            view=self,
            queryset=queryset,
            serializer_class=ChurchPastoralCareCaseListSerializer,
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        ensure_pastoral_manage_permission(
            actor=request.user,
            workspace=workspace,
            require_write=True,
        )

        serializer = ChurchPastoralCareCaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        congregant = get_church_congregant_or_404(
            workspace=workspace,
            public_id=data.pop("congregant_public_id"),
        )

        try:
            care_case = create_pastoral_care_case(
                workspace=workspace,
                congregant=congregant,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=care_case.public_id,
        )
        return Response(
            _serialize(ChurchPastoralCareCaseSerializer, care_case, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchPastoralCareCaseDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        return Response(
            _serialize(ChurchPastoralCareCaseSerializer, care_case, request)
        )


class ChurchPastoralCareAssignmentsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        assignments = (
            care_case.assignments
            .select_related("membership__member__user")
            .order_by("-assigned_at", "-id")
        )
        return Response(
            _serialize(
                ChurchPastoralCareAssignmentSerializer,
                assignments,
                request,
                many=True,
            )
        )

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_manageable_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        serializer = ChurchPastoralCareAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        membership = get_organization_membership_or_404(
            organization=workspace.activation.organization,
            public_id=data.pop("membership_public_id"),
        )

        try:
            assignment = assign_pastoral_care_case(
                care_case=care_case,
                membership=membership,
                actor=request.user,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchPastoralCareAssignmentSerializer, assignment, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchPastoralCareAssignmentEndView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        assignment = _get_manageable_assignment_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        try:
            assignment = end_pastoral_care_assignment(
                assignment=assignment,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchPastoralCareAssignmentSerializer, assignment, request)
        )


class ChurchPastoralCareNotesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        notes = list_pastoral_care_notes_for_actor(
            care_case=care_case,
            actor=request.user,
        )
        return _paginate(
            request=request,
            view=self,
            queryset=notes,
            serializer_class=ChurchPastoralCareNoteSerializer,
        )

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        serializer = ChurchPastoralCareNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        amends_note = _get_visible_amended_note_or_404(
            care_case=care_case,
            actor=request.user,
            public_id=data.pop("amends_note_public_id", None),
        )

        try:
            note = add_pastoral_care_note(
                care_case=care_case,
                actor=request.user,
                amends_note=amends_note,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchPastoralCareNoteSerializer, note, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchPastoralCareContactsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        contacts = (
            ChurchPastoralCareContact.objects
            .filter(case=care_case)
            .select_related("actor_membership__member__user")
            .order_by("-occurred_at", "-id")
        )
        return _paginate(
            request=request,
            view=self,
            queryset=contacts,
            serializer_class=ChurchPastoralCareContactSerializer,
        )

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        serializer = ChurchPastoralCareContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            contact = record_pastoral_care_contact(
                care_case=care_case,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchPastoralCareContactSerializer, contact, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchPastoralCareHoldView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_manageable_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        try:
            care_case = put_pastoral_care_case_on_hold(
                care_case=care_case,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=care_case.public_id,
        )
        return Response(
            _serialize(ChurchPastoralCareCaseSerializer, care_case, request)
        )


class ChurchPastoralCareReopenView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_manageable_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        try:
            care_case = reopen_pastoral_care_case(
                care_case=care_case,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=care_case.public_id,
        )
        return Response(
            _serialize(ChurchPastoralCareCaseSerializer, care_case, request)
        )


class ChurchPastoralCareCloseView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        care_case = _get_manageable_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=public_id,
        )
        serializer = ChurchPastoralCareCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            care_case = close_pastoral_care_case(
                care_case=care_case,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        care_case = _get_visible_case_or_404(
            workspace=workspace,
            actor=request.user,
            public_id=care_case.public_id,
        )
        return Response(
            _serialize(ChurchPastoralCareCaseSerializer, care_case, request)
        )
