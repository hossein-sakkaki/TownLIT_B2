# apps/organizations/modules/church/views/teaching.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.core.pagination import ConfigurablePagination
from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.models import OrganizationMembership
from apps.organizations.modules.church.constants import (
    ChurchPermissionKey,
    ChurchServicePlanItemType,
    ChurchServicePlanStatus,
    ChurchTeachingAudience,
    ChurchTeachingContentType,
    ChurchTeachingFormat,
    ChurchTeachingSeriesStatus,
    ChurchTeachingStatus,
)
from apps.organizations.modules.church.models import (
    ChurchServicePlanItem,
    ChurchTeachingSeries,
)
from apps.organizations.modules.church.selectors.church import (
    list_active_church_campuses,
    list_active_church_ministries,
    list_upcoming_church_gatherings,
)
from apps.organizations.modules.church.selectors.teaching import (
    list_church_teaching_series,
    list_visible_church_teaching_contents,
)
from apps.organizations.modules.church.serializers import (
    ChurchCampusSerializer,
    ChurchGatheringOccurrenceSerializer,
    ChurchMinistrySerializer,
    ChurchTeachingContentCreateSerializer,
    ChurchTeachingContentSerializer,
    ChurchTeachingContentUpdateSerializer,
    ChurchTeachingSeriesCreateSerializer,
    ChurchTeachingSeriesSerializer,
    ChurchTeachingSeriesUpdateSerializer,
)
from apps.organizations.modules.church.services.access import (
    ensure_church_permission,
    user_has_church_permission,
)
from apps.organizations.modules.church.services.teaching import (
    archive_church_teaching_content,
    archive_church_teaching_series,
    create_church_teaching_content,
    create_church_teaching_series,
    delete_draft_church_teaching_content,
    publish_church_teaching_content,
    update_church_teaching_content,
    update_church_teaching_series,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.views.helpers import raise_drf_validation_error
from apps.posts.models.church_teaching import ChurchTeachingContent

from .helpers import (
    get_church_campus_or_404,
    get_church_gathering_or_404,
    get_church_ministry_or_404,
    get_church_request_context,
    get_organization_membership_or_404,
)


class ChurchTeachingPagination(ConfigurablePagination):
    page_size = 20
    max_page_size = 50


TEACHING_STAFF_PERMISSION_KEYS = (
    ChurchPermissionKey.VIEW_TEACHING,
    ChurchPermissionKey.MANAGE_TEACHING,
    ChurchPermissionKey.PUBLISH_TEACHING,
)


def _serialize(serializer_class, instance, request):
    return serializer_class(
        instance,
        context={"request": request},
    ).data


def _paginate(*, request, view, queryset):
    paginator = ChurchTeachingPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    serializer = ChurchTeachingContentSerializer(
        page,
        many=True,
        context={"request": request},
    )
    return paginator.get_paginated_response(serializer.data)


def _has_teaching_staff_access(*, user, workspace):
    return any(
        user_has_church_permission(
            user=user,
            workspace=workspace,
            permission_key=permission_key,
        )
        for permission_key in TEACHING_STAFF_PERMISSION_KEYS
    )


def _ensure_teaching_manage(*, user, workspace, require_write=True):
    ensure_church_permission(
        actor=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
        require_write=require_write,
    )


def _ensure_teaching_publish(*, user, workspace, require_write=True):
    ensure_church_permission(
        actor=user,
        workspace=workspace,
        permission_key=ChurchPermissionKey.PUBLISH_TEACHING,
        require_write=require_write,
    )


def _get_series_or_404(*, workspace, public_id):
    series = (
        ChurchTeachingSeries.objects
        .select_related("workspace__activation__organization", "campus", "ministry")
        .filter(workspace=workspace, public_id=public_id)
        .first()
    )
    if not series:
        raise NotFound("Church teaching series not found.")
    return series


def _get_content_or_404(*, workspace, public_id):
    content = (
        ChurchTeachingContent.objects
        .select_related(
            "workspace__activation__organization",
            "series",
            "campus",
            "ministry",
            "occurrence",
            "service_plan_item__service_plan__occurrence",
            "speaker_membership__member__user",
        )
        .prefetch_related("scripture_references")
        .filter(workspace=workspace, public_id=public_id)
        .first()
    )
    if not content:
        raise NotFound("Church teaching content not found.")
    return content


def _get_visible_content_or_404(*, workspace, viewer, public_id):
    include_manager_preview = _has_teaching_staff_access(
        user=viewer,
        workspace=workspace,
    )
    content = (
        list_visible_church_teaching_contents(
            workspace=workspace,
            viewer=viewer,
            include_manager_drafts=include_manager_preview,
        )
        .filter(public_id=public_id)
        .first()
    )
    if not content:
        raise NotFound("Church teaching content not found.")
    return content


def _resolve_optional_series(*, workspace, public_id):
    if public_id is None:
        return None
    return _get_series_or_404(workspace=workspace, public_id=public_id)


def _resolve_optional_campus(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_campus_or_404(workspace=workspace, public_id=public_id)


def _resolve_optional_ministry(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_ministry_or_404(workspace=workspace, public_id=public_id)


def _resolve_optional_occurrence(*, workspace, public_id):
    if public_id is None:
        return None
    return get_church_gathering_or_404(workspace=workspace, public_id=public_id)


def _resolve_optional_service_plan_item(*, workspace, public_id):
    if public_id is None:
        return None

    item = (
        ChurchServicePlanItem.objects
        .select_related("service_plan__workspace", "service_plan__occurrence")
        .filter(
            service_plan__workspace=workspace,
            public_id=public_id,
            item_type=ChurchServicePlanItemType.SERMON,
        )
        .first()
    )
    if not item:
        raise NotFound("Church sermon service plan item not found.")
    return item


def _resolve_optional_speaker_membership(*, organization, public_id):
    if public_id is None:
        return None

    membership = get_organization_membership_or_404(
        organization=organization,
        public_id=public_id,
    )
    if membership.status != OrganizationMembershipStatus.ACTIVE:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({
            "speaker_membership_public_id": "Church teaching speakers require an active official Organization membership.",
        })
    return membership


def _apply_content_filters(*, queryset, request):
    query = " ".join(str(request.query_params.get("q") or "").split())
    teaching_type = request.query_params.get("teaching_type")
    content_format = request.query_params.get("format")
    status_value = request.query_params.get("status")
    audience = request.query_params.get("audience")
    series_public_id = request.query_params.get("series")
    campus_public_id = request.query_params.get("campus")
    ministry_public_id = request.query_params.get("ministry")

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(excerpt__icontains=query)
            | Q(speaker_name_snapshot__icontains=query)
            | Q(scripture_references__reference_text__icontains=query)
        ).distinct()

    if teaching_type:
        valid = {value for value, _ in ChurchTeachingContentType.choices}
        if teaching_type not in valid:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"teaching_type": "Unsupported Church teaching type."})
        queryset = queryset.filter(teaching_type=teaching_type)

    if content_format:
        valid = {value for value, _ in ChurchTeachingFormat.choices}
        if content_format not in valid:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"format": "Unsupported Church teaching format."})
        queryset = queryset.filter(content_format=content_format)

    if status_value:
        valid = {value for value, _ in ChurchTeachingStatus.choices}
        if status_value not in valid:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"status": "Unsupported Church teaching status."})
        queryset = queryset.filter(status=status_value)

    if audience:
        valid = {value for value, _ in ChurchTeachingAudience.choices}
        if audience not in valid:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"audience": "Unsupported Church teaching audience."})
        queryset = queryset.filter(audience=audience)

    if series_public_id:
        queryset = queryset.filter(series__public_id=series_public_id)
    if campus_public_id:
        queryset = queryset.filter(campus__public_id=campus_public_id)
    if ministry_public_id:
        queryset = queryset.filter(ministry__public_id=ministry_public_id)

    return queryset


def _create_context_objects(*, workspace, organization, data):
    return {
        "series": _resolve_optional_series(
            workspace=workspace,
            public_id=data.pop("series_public_id", None),
        ),
        "campus": _resolve_optional_campus(
            workspace=workspace,
            public_id=data.pop("campus_public_id", None),
        ),
        "ministry": _resolve_optional_ministry(
            workspace=workspace,
            public_id=data.pop("ministry_public_id", None),
        ),
        "occurrence": _resolve_optional_occurrence(
            workspace=workspace,
            public_id=data.pop("occurrence_public_id", None),
        ),
        "service_plan_item": _resolve_optional_service_plan_item(
            workspace=workspace,
            public_id=data.pop("service_plan_item_public_id", None),
        ),
        "speaker_membership": _resolve_optional_speaker_membership(
            organization=organization,
            public_id=data.pop("speaker_membership_public_id", None),
        ),
    }


def _update_context_kwargs(*, workspace, organization, validated_data):
    data = dict(validated_data)
    kwargs = {}

    resolvers = {
        "series_public_id": ("series", lambda value: _resolve_optional_series(workspace=workspace, public_id=value)),
        "campus_public_id": ("campus", lambda value: _resolve_optional_campus(workspace=workspace, public_id=value)),
        "ministry_public_id": ("ministry", lambda value: _resolve_optional_ministry(workspace=workspace, public_id=value)),
        "occurrence_public_id": ("occurrence", lambda value: _resolve_optional_occurrence(workspace=workspace, public_id=value)),
        "service_plan_item_public_id": ("service_plan_item", lambda value: _resolve_optional_service_plan_item(workspace=workspace, public_id=value)),
        "speaker_membership_public_id": ("speaker_membership", lambda value: _resolve_optional_speaker_membership(organization=organization, public_id=value)),
    }

    for input_key, (service_key, resolver) in resolvers.items():
        if input_key in data:
            kwargs[service_key] = resolver(data.pop(input_key))

    kwargs.update(data)
    return kwargs


class ChurchTeachingReferencesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization, workspace, _ = get_church_request_context(
            user=request.user,
            slug=slug,
        )
        _ensure_teaching_manage(
            user=request.user,
            workspace=workspace,
            require_write=False,
        )

        memberships = (
            OrganizationMembership.objects
            .select_related("member__user")
            .filter(
                organization=organization,
                status=OrganizationMembershipStatus.ACTIVE,
            )
            .order_by("member__user__name", "member__user__family", "id")
        )

        speakers = [
            {
                "membership_public_id": str(membership.public_id),
                "user": UserMiniSerializer(
                    membership.member.user,
                    context={"request": request},
                ).data,
            }
            for membership in memberships
        ]

        service_items = (
            ChurchServicePlanItem.objects
            .filter(
                service_plan__workspace=workspace,
                service_plan__status__in={
                    ChurchServicePlanStatus.DRAFT,
                    ChurchServicePlanStatus.PUBLISHED,
                },
                item_type=ChurchServicePlanItemType.SERMON,
            )
            .select_related("service_plan__occurrence")
            .order_by("service_plan__occurrence__starts_at", "sort_order", "id")
        )

        service_item_payload = [
            {
                "public_id": str(item.public_id),
                "title": item.title,
                "service_plan_public_id": str(item.service_plan.public_id),
                "occurrence_public_id": str(item.service_plan.occurrence.public_id),
                "occurrence_title": item.service_plan.occurrence.title,
                "starts_at": item.service_plan.occurrence.starts_at,
            }
            for item in service_items
        ]

        return Response({
            "series": ChurchTeachingSeriesSerializer(
                list_church_teaching_series(
                    workspace=workspace,
                    include_archived=False,
                ),
                many=True,
                context={"request": request},
            ).data,
            "campuses": ChurchCampusSerializer(
                list_active_church_campuses(workspace=workspace),
                many=True,
                context={"request": request},
            ).data,
            "ministries": ChurchMinistrySerializer(
                list_active_church_ministries(workspace=workspace),
                many=True,
                context={"request": request},
            ).data,
            "upcoming_gatherings": ChurchGatheringOccurrenceSerializer(
                list_upcoming_church_gatherings(workspace=workspace)[:100],
                many=True,
                context={"request": request},
            ).data,
            "speakers": speakers,
            "sermon_service_plan_items": service_item_payload,
        })


class ChurchTeachingSeriesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        management = str(request.query_params.get("management") or "").lower() in {"1", "true", "yes"}
        staff_access = _has_teaching_staff_access(user=request.user, workspace=workspace)

        if management and staff_access:
            queryset = list_church_teaching_series(
                workspace=workspace,
                include_archived=True,
            )
        else:
            visible_content = list_visible_church_teaching_contents(
                workspace=workspace,
                viewer=request.user,
                include_manager_drafts=False,
            ).exclude(series__isnull=True)
            queryset = (
                list_church_teaching_series(
                    workspace=workspace,
                    include_archived=False,
                )
                .filter(id__in=visible_content.values("series_id"))
            )

        return Response(
            ChurchTeachingSeriesSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_manage(user=request.user, workspace=workspace)

        serializer = ChurchTeachingSeriesCreateSerializer(data=request.data)
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
            series = create_church_teaching_series(
                workspace=workspace,
                actor=request.user,
                campus=campus,
                ministry=ministry,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            _serialize(ChurchTeachingSeriesSerializer, series, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchTeachingSeriesDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        series = _get_series_or_404(workspace=workspace, public_id=public_id)

        if not _has_teaching_staff_access(user=request.user, workspace=workspace):
            visible = list_visible_church_teaching_contents(
                workspace=workspace,
                viewer=request.user,
                include_manager_drafts=False,
            ).filter(series=series).exists()
            if not visible:
                raise NotFound("Church teaching series not found.")

        return Response(_serialize(ChurchTeachingSeriesSerializer, series, request))

    def patch(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_manage(user=request.user, workspace=workspace)
        series = _get_series_or_404(workspace=workspace, public_id=public_id)

        serializer = ChurchTeachingSeriesUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        kwargs = dict(data)
        if "campus_public_id" in data:
            kwargs["campus"] = _resolve_optional_campus(
                workspace=workspace,
                public_id=data["campus_public_id"],
            )
            kwargs.pop("campus_public_id", None)
        if "ministry_public_id" in data:
            kwargs["ministry"] = _resolve_optional_ministry(
                workspace=workspace,
                public_id=data["ministry_public_id"],
            )
            kwargs.pop("ministry_public_id", None)

        try:
            series = update_church_teaching_series(
                series=series,
                actor=request.user,
                **kwargs,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchTeachingSeriesSerializer, series, request))


class ChurchTeachingSeriesArchiveView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_publish(user=request.user, workspace=workspace)
        series = _get_series_or_404(workspace=workspace, public_id=public_id)

        try:
            series = archive_church_teaching_series(
                series=series,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(_serialize(ChurchTeachingSeriesSerializer, series, request))


class ChurchTeachingContentsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        management = str(request.query_params.get("management") or "").lower() in {"1", "true", "yes"}

        queryset = list_visible_church_teaching_contents(
            workspace=workspace,
            viewer=request.user,
            include_manager_drafts=management,
        )
        queryset = _apply_content_filters(queryset=queryset, request=request)
        return _paginate(request=request, view=self, queryset=queryset)

    def post(self, request, slug):
        organization, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_manage(user=request.user, workspace=workspace)

        serializer = ChurchTeachingContentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        context_objects = _create_context_objects(
            workspace=workspace,
            organization=organization,
            data=data,
        )

        try:
            content = create_church_teaching_content(
                workspace=workspace,
                actor=request.user,
                **context_objects,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        content = _get_content_or_404(workspace=workspace, public_id=content.public_id)
        return Response(
            _serialize(ChurchTeachingContentSerializer, content, request),
            status=status.HTTP_201_CREATED,
        )


class ChurchTeachingContentDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        content = _get_visible_content_or_404(
            workspace=workspace,
            viewer=request.user,
            public_id=public_id,
        )
        return Response(_serialize(ChurchTeachingContentSerializer, content, request))

    def patch(self, request, slug, public_id):
        organization, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_manage(user=request.user, workspace=workspace)
        content = _get_content_or_404(workspace=workspace, public_id=public_id)

        serializer = ChurchTeachingContentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        kwargs = _update_context_kwargs(
            workspace=workspace,
            organization=organization,
            validated_data=serializer.validated_data,
        )

        try:
            content = update_church_teaching_content(
                content=content,
                actor=request.user,
                **kwargs,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        content = _get_content_or_404(workspace=workspace, public_id=content.public_id)
        return Response(_serialize(ChurchTeachingContentSerializer, content, request))

    def delete(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_manage(user=request.user, workspace=workspace)
        content = _get_content_or_404(workspace=workspace, public_id=public_id)

        try:
            delete_draft_church_teaching_content(
                content=content,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ChurchTeachingContentPublishView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_publish(user=request.user, workspace=workspace)
        content = _get_content_or_404(workspace=workspace, public_id=public_id)

        try:
            content = publish_church_teaching_content(
                content=content,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        content = _get_content_or_404(workspace=workspace, public_id=content.public_id)
        return Response(_serialize(ChurchTeachingContentSerializer, content, request))


class ChurchTeachingContentArchiveView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, slug, public_id):
        _, workspace, _ = get_church_request_context(user=request.user, slug=slug)
        _ensure_teaching_publish(user=request.user, workspace=workspace)
        content = _get_content_or_404(workspace=workspace, public_id=public_id)

        try:
            content = archive_church_teaching_content(
                content=content,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        content = _get_content_or_404(workspace=workspace, public_id=content.public_id)
        return Response(_serialize(ChurchTeachingContentSerializer, content, request))
