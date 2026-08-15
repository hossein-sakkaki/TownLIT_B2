# apps/posts/views/journeys.py

from __future__ import annotations

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Avg, Count, Prefetch, Q
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.services.username_resolution import resolve_username
from apps.core.boundaries.query import BoundaryVisibilityQuery
from apps.core.ownership.owner_gate_mixins import OwnerGateMixin
from apps.core.ownership.utils import resolve_owner_from_request
from apps.core.pagination import ConfigurablePagination
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.visibility.query import VisibilityQuery

from apps.posts.models.journey import Journey, JourneyEntry
from apps.posts.constants.journeys import JourneyViewSource
from apps.posts.serializers.journeys import (
    JourneyAnalyticsSerializer,
    JourneyCloseSerializer,
    JourneyCreationStatusSerializer,
    JourneyEntrySerializer,
    JourneyProfileMapSerializer,
    JourneyProfileRingSerializer,
    JourneyPublishSerializer,
    JourneySerializer,
    JourneyViewerSerializer,
    JourneyViewWriteSerializer,
)
from apps.posts.services.journeys.journey_content_safety import (
    enforce_journey_close_content_safety,
    enforce_owned_journey_composition_content_safety,
)
from apps.journey_insights.services.daily_prompt import (
    DailyReflectionPromptResult,
    resolve_daily_reflection_after_publish,
)
from apps.posts.services.journeys.profile_ring import (
    build_journey_profile_ring,
    empty_journey_profile_ring,
)
from apps.profiles.models.member import Member
from apps.posts.services.journeys.creation_status import (
    get_journey_creation_status,
)
from apps.creative_editor.models import CreativeComposition
from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
)
from apps.media_conversion.serializers import (
    MediaConversionJobSerializer,
)
from apps.posts.serializers.journeys import JourneySubmitSerializer
from apps.posts.services.journeys.processing import (
    JOURNEY_WORKFLOW_FIELD,
    submit_journey_workflow,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Journey Pagination
# ------------------------------------------------------------
class JourneyPagination(ConfigurablePagination):
    page_size = 12
    max_page_size = 30


class JourneyViewSet(
    OwnerGateMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """
    Daily Journey chapters.
    """

    serializer_class = JourneySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JourneyPagination
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in {
            "retrieve",
            "profile_ring",
            "profile_map",
        }:
            return [AllowAny()]

        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in {
            "my_ring",
            "profile_ring",
        }:
            return JourneyProfileRingSerializer

        if self.action == "profile_map":
            return JourneyProfileMapSerializer

        return JourneySerializer

    def _detail_entry_queryset(self):
        """
        Full Entry queryset for detail/archive.
        """

        return (
            JourneyEntry.objects.select_related(
                "journey",
                "content_type",
                "composition",
                "render_job",
                "music_track",
                "music_variant",
                "music_track__catalog",
                "music_track__rights",
            )
            .prefetch_related(
                "music_track__contributor_links__contributor",
            )
            .order_by("sequence", "id")
        )

    def _stream_entry_queryset(self):
        """
        Stream Entry queryset with canonical Audio Catalog data.
        """

        return (
            JourneyEntry.objects
            .select_related(
                "journey",
                "music_track",
                "music_variant",
                "music_track__catalog",
                "music_track__rights",
            )
            .prefetch_related(
                "music_track__contributor_links__contributor",
            )
            .order_by(
                "sequence",
                "id",
            )
        )

    def _journey_queryset_with_entries(
        self,
        *,
        entry_queryset,
    ):
        """
        Build Journey queryset with controlled prefetch.
        """

        return (
            Journey.objects.select_related("content_type")
            .prefetch_related(
                Prefetch(
                    "entries",
                    queryset=entry_queryset,
                    to_attr="ordered_entries",
                )
            )
            .order_by("-local_date", "-id")
        )

    def get_queryset(self):
        entries = self._detail_entry_queryset().filter(
            is_active=True,
            is_hidden=False,
        )

        return self._journey_queryset_with_entries(
            entry_queryset=entries,
        )

    def _request_member(self):
        """
        Resolve active Member owner.
        """

        owner = resolve_owner_from_request(self.request)

        if not isinstance(owner, Member):
            raise PermissionDenied(
                "Only Member profiles support Journey."
            )

        return owner

    @staticmethod
    def _is_entry_owner(
        *,
        request,
        entry: JourneyEntry,
    ) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        owner = resolve_owner_from_request(request)

        if owner is None:
            return False

        owner_ct = ContentType.objects.get_for_model(
            owner.__class__,
            for_concrete_model=False,
        )

        return bool(
            entry.content_type_id == owner_ct.pk
            and entry.object_id == owner.pk
        )

    def retrieve(
        self,
        request,
        *args,
        **kwargs,
    ):
        journey = self.get_object()
        now = timezone.now()
        visible_entries = []

        for entry in journey.ordered_entries:
            self.apply_hard_owner_gate(request, entry)

            is_owner = self._is_entry_owner(
                request=request,
                entry=entry,
            )

            if not is_owner:
                if entry.archived_at is not None:
                    continue

                if entry.published_at > now:
                    continue

                if entry.expires_at <= now:
                    continue

            if VisibilityPolicy.can_view(
                viewer=request.user,
                obj=entry,
            ):
                visible_entries.append(entry)

        if not visible_entries:
            raise NotFound("Journey not found.")

        journey.ordered_entries = visible_entries

        return Response(
            self.get_serializer(journey).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="creation-status",
    )
    def creation_status(self, request):
        owner = resolve_owner_from_request(request)

        if owner is None:
            return Response(
                {
                    "detail": "A valid Journey owner is required.",
                    "code": "invalid_journey_owner",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        requested_timezone = (
            request.query_params.get("timezone") or ""
        ).strip() or None

        try:
            result = get_journey_creation_status(
                user=request.user,
                owner=owner,
                requested_timezone=requested_timezone,
            )
        except DjangoValidationError as exc:
            logger.warning(
                "journey.creation_status.denied user_id=%s errors=%s",
                getattr(request.user, "pk", None),
                (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else exc.messages
                ),
            )

            return Response(
                {
                    "detail": "Journey creation is not available.",
                    "code": "journey_creation_unavailable",
                    "errors": (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = JourneyCreationStatusSerializer(
            instance=result.as_dict()
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
        
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="publish",
    )
    def publish(self, request):
        serializer = JourneyPublishSerializer(
            data=request.data,
            context={"request": request},
        )

        if not serializer.is_valid():
            logger.warning(
                (
                    "journey.publish.invalid "
                    "user_id=%s "
                    "composition_id=%r "
                    "render_job_id=%r "
                    "revision=%r "
                    "visibility=%r "
                    "retention=%r "
                    "has_music=%s "
                    "errors=%s"
                ),
                getattr(request.user, "pk", None),
                request.data.get("composition_id"),
                request.data.get("render_job_id"),
                request.data.get("composition_revision"),
                request.data.get("visibility"),
                request.data.get("retention_policy"),
                bool(request.data.get("music_track_id")),
                serializer.errors,
            )

            return Response(
                {
                    "detail": "Journey publish data is invalid.",
                    "code": "journey_publish_invalid",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        enforce_owned_journey_composition_content_safety(
            composition_id=serializer.validated_data[
                "composition_id"
            ],
            actor=request.user,
        )

        publish_context = {
            "user_id": getattr(request.user, "pk", None),
            "composition_id": serializer.validated_data.get(
                "composition_id"
            ),
            "render_job_id": serializer.validated_data.get(
                "render_job_id"
            ),
            "composition_revision": serializer.validated_data.get(
                "composition_revision"
            ),
            "visibility": serializer.validated_data.get("visibility"),
        }

        try:
            result = serializer.save()
        except Exception:
            logger.exception(
                (
                    "journey.publish.service_failed "
                    "user_id=%s "
                    "composition_id=%s "
                    "render_job_id=%s "
                    "revision=%s "
                    "visibility=%s"
                ),
                publish_context["user_id"],
                publish_context["composition_id"],
                publish_context["render_job_id"],
                publish_context["composition_revision"],
                publish_context["visibility"],
            )
            raise

        try:
            daily_reflection = resolve_daily_reflection_after_publish(
                user=request.user,
                journey=result.journey,
                entry=result.entry,
            )
        except Exception:
            logger.exception(
                (
                    "journey.publish.reflection_failed "
                    "user_id=%s journey_id=%s entry_id=%s"
                ),
                publish_context["user_id"],
                getattr(result.journey, "pk", None),
                getattr(result.entry, "pk", None),
            )

            daily_reflection = DailyReflectionPromptResult(
                should_present=False,
                reason="reflection_unavailable",
                prompt_public_id=None,
                local_date=result.journey.local_date,
                timezone_name=result.journey.timezone_name,
                status=None,
                session_public_id=None,
                session_question_public_id=None,
                question_public_id=None,
                question_code=None,
                prompt=None,
                kind=None,
                choices=[],
                prompt_count=0,
                deferred_count=0,
            )

        try:
            result.journey.ordered_entries = list(
                self._detail_entry_queryset().filter(
                    journey=result.journey,
                    is_active=True,
                    is_hidden=False,
                )
            )

            journey_data = JourneySerializer(
                result.journey,
                context={"request": request},
            ).data

            entry_data = JourneyEntrySerializer(
                result.entry,
                context={"request": request},
            ).data

            daily_reflection_data = daily_reflection.as_dict()
        except Exception:
            logger.exception(
                (
                    "journey.publish.response_failed "
                    "user_id=%s "
                    "journey_id=%s "
                    "entry_id=%s"
                ),
                publish_context["user_id"],
                getattr(result.journey, "pk", None),
                getattr(result.entry, "pk", None),
            )
            raise

        return Response(
            {
                "journey": journey_data,
                "entry": entry_data,
                "created_journey": result.created_journey,
                "daily_reflection": daily_reflection_data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="active",
    )
    def active(self, request):
        """
        Return full visible live Journeys.
        """

        now = timezone.now()

        entries = self._detail_entry_queryset().filter(
            is_active=True,
            is_hidden=False,
            is_suspended=False,
            published_at__lte=now,
            expires_at__gt=now,
            archived_at__isnull=True,
        )

        entries = VisibilityQuery.for_viewer(
            viewer=request.user,
            base_queryset=entries,
        )

        entries = BoundaryVisibilityQuery.exclude_boundary_conflicts(
            entries,
            viewer=request.user,
        )

        entry_ids = list(
            entries.values_list("id", flat=True)
        )

        if not entry_ids:
            return Response(
                [],
                status=status.HTTP_200_OK,
            )

        journey_ids = list(
            entries.values_list(
                "journey_id",
                flat=True,
            ).distinct()
        )

        prefetch_entries = self._detail_entry_queryset().filter(
            id__in=entry_ids,
        )

        journeys = self._journey_queryset_with_entries(
            entry_queryset=prefetch_entries,
        ).filter(
            id__in=journey_ids,
        )

        page = self.paginate_queryset(journeys)
        serializer = self.get_serializer(page, many=True)

        return self.get_paginated_response(serializer.data)


    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="me",
    )
    def me(self, request):
        """
        Return owner Journey chapters.
        """

        member = self._request_member()

        member_ct = ContentType.objects.get_for_model(
            Member,
            for_concrete_model=False,
        )

        owner_entries = self._detail_entry_queryset().filter(
            content_type=member_ct,
            object_id=member.pk,
        )

        queryset = self._journey_queryset_with_entries(
            entry_queryset=owner_entries,
        ).filter(
            content_type=member_ct,
            object_id=member.pk,
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="archive",
    )
    def archive(self, request):
        """
        Return archived owner Journeys.
        """

        member = self._request_member()

        member_ct = ContentType.objects.get_for_model(
            Member,
            for_concrete_model=False,
        )

        archived_entries = self._detail_entry_queryset().filter(
            content_type=member_ct,
            object_id=member.pk,
            archived_at__isnull=False,
        )

        journey_ids = list(
            archived_entries.values_list(
                "journey_id",
                flat=True,
            ).distinct()
        )

        journeys = self._journey_queryset_with_entries(
            entry_queryset=archived_entries,
        ).filter(
            id__in=journey_ids,
            content_type=member_ct,
            object_id=member.pk,
        )

        page = self.paginate_queryset(journeys)
        serializer = self.get_serializer(page, many=True)

        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="my-ring",
    )
    def my_ring(self, request):
        """
        Return current owner's profile Ring.
        """

        member = self._request_member()

        result = build_journey_profile_ring(
            owner_profile=member,
            viewer=request.user,
            owner_can_see_all=True,
        )

        return Response(
            JourneyProfileRingSerializer(
                result,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path=r"profile-ring/(?P<username>[^/]+)",
    )
    def profile_ring(
        self,
        request,
        username=None,
    ):
        """
        Return a Member profile Journey Ring.
        """

        resolved = resolve_username(
            username,
            include_deleted=False,
        )

        if resolved is None:
            raise NotFound("Profile not found.")

        member = (
            Member.objects.select_related("user")
            .filter(
                user_id=resolved.user.pk,
                is_active=True,
            )
            .first()
        )

        if member is None:
            result = empty_journey_profile_ring()
        else:
            viewer = (
                request.user
                if request.user.is_authenticated
                else None
            )

            result = build_journey_profile_ring(
                owner_profile=member,
                viewer=viewer,
            )

        response = Response(
            JourneyProfileRingSerializer(
                result,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

        response[
            "X-TownLIT-Canonical-Username"
        ] = resolved.canonical_username

        response[
            "X-TownLIT-Username-Alias-Resolved"
        ] = "1" if resolved.was_alias else "0"

        return response

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path=r"profile-map/(?P<username>[^/]+)",
    )
    def profile_map(
        self,
        request,
        username=None,
    ):
        """
        Return current and retained historical Journeys
        for one Member profile.

        Owner:
        - sees all eligible own Entries

        Visitor:
        - sees only Entries allowed by visibility
        and boundary policies
        """

        resolved = resolve_username(
            username,
            include_deleted=False,
        )

        if resolved is None:
            raise NotFound(
                "Profile not found."
            )

        member = (
            Member.objects
            .select_related(
                "user",
            )
            .filter(
                user_id=resolved.user.pk,
                is_active=True,
            )
            .first()
        )

        if member is None:
            raise NotFound(
                "Member profile not found."
            )

        member_ct = (
            ContentType.objects
            .get_for_model(
                Member,
                for_concrete_model=False,
            )
        )

        viewer = (
            request.user
            if request.user.is_authenticated
            else None
        )

        is_owner = bool(
            viewer is not None
            and viewer.pk == member.user_id
        )

        entries = (
            self._stream_entry_queryset()
            .filter(
                content_type=member_ct,
                object_id=member.pk,
                is_active=True,
                is_hidden=False,
                is_suspended=False,
                published_at__lte=timezone.now(),
            )
        )

        if not is_owner:
            entries = VisibilityQuery.for_viewer(
                viewer=viewer,
                base_queryset=entries,
            )

            if viewer is not None:
                entries = (
                    BoundaryVisibilityQuery
                    .exclude_boundary_conflicts(
                        entries,
                        viewer=viewer,
                    )
                )

        visible_entry_ids = list(
            entries.values_list(
                "id",
                flat=True,
            )
        )

        if not visible_entry_ids:
            response = Response(
                {
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "results": [],
                },
                status=status.HTTP_200_OK,
            )

            response[
                "X-TownLIT-Canonical-Username"
            ] = resolved.canonical_username

            response[
                "X-TownLIT-Username-Alias-Resolved"
            ] = (
                "1"
                if resolved.was_alias
                else "0"
            )

            return response

        journey_ids = list(
            entries.values_list(
                "journey_id",
                flat=True,
            ).distinct()
        )

        prefetch_entries = (
            self._stream_entry_queryset()
            .filter(
                id__in=visible_entry_ids,
            )
        )

        journeys = (
            self._journey_queryset_with_entries(
                entry_queryset=prefetch_entries,
            )
            .filter(
                id__in=journey_ids,
                content_type=member_ct,
                object_id=member.pk,
            )
            .order_by(
                "-local_date",
                "-id",
            )
        )

        page = self.paginate_queryset(
            journeys
        )

        today_by_timezone: dict[
            str,
            object,
        ] = {}

        for journey in page:
            timezone_name = (
                journey.timezone_name
                or "UTC"
            )

            local_today = (
                today_by_timezone.get(
                    timezone_name
                )
            )

            if local_today is None:
                try:
                    from zoneinfo import ZoneInfo

                    local_today = (
                        timezone.now()
                        .astimezone(
                            ZoneInfo(
                                timezone_name
                            )
                        )
                        .date()
                    )
                except Exception:
                    local_today = (
                        timezone.localdate()
                    )

                today_by_timezone[
                    timezone_name
                ] = local_today

            journey._journey_profile_is_active_today = (
                journey.local_date
                == local_today
            )

        serializer = self.get_serializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        response = self.get_paginated_response(
            serializer.data
        )

        response[
            "X-TownLIT-Canonical-Username"
        ] = resolved.canonical_username

        response[
            "X-TownLIT-Username-Alias-Resolved"
        ] = (
            "1"
            if resolved.was_alias
            else "0"
        )

        return response

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="close",
    )
    def close(
        self,
        request,
        slug=None,
    ):
        journey = self.get_object()
        member = self._request_member()

        member_ct = ContentType.objects.get_for_model(
            Member,
            for_concrete_model=False,
        )

        if (
            journey.content_type_id != member_ct.pk
            or journey.object_id != member.pk
        ):
            raise PermissionDenied(
                "You do not own this Journey."
            )

        serializer = JourneyCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        close_text = serializer.validated_data[
            "text"
        ]

        close_is_private = serializer.validated_data[
            "is_private"
        ]

        enforce_journey_close_content_safety(
            text=close_text,
            is_private=close_is_private,
            actor=request.user,
        )

        journey.close(
            text=close_text,
            is_private=close_is_private,
        )

        journey.ordered_entries = list(
            self._detail_entry_queryset().filter(
                journey=journey,
            )
        )

        return Response(
            JourneySerializer(
                journey,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="submit",
    )
    def submit(self, request):
        serializer = JourneySubmitSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True
        )

        owner = self._request_member()

        # Content Safety runs synchronously before Journey enters
        # the asynchronous render/publish workflow.
        enforce_owned_journey_composition_content_safety(
            composition_id=serializer.validated_data[
                "composition_id"
            ],
            actor=request.user,
        )

        try:
            job, created = submit_journey_workflow(
                user=request.user,
                owner=owner,
                validated_data=dict(
                    serializer.validated_data
                ),
            )

        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": "Journey submission is unavailable.",
                    "code": "journey_submission_invalid",
                    "errors": (
                        exc.message_dict
                        if hasattr(
                            exc,
                            "message_dict",
                        )
                        else exc.messages
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            MediaConversionJobSerializer(
                job,
                context={
                    "request": request,
                },
            ).data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )


    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="processing-jobs",
    )
    def processing_jobs(self, request):
        member = self._request_member()

        composition_ids = (
            CreativeComposition.objects
            .filter(
                owner=request.user,
                is_active=True,
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

        content_type = ContentType.objects.get_for_model(
            CreativeComposition,
            for_concrete_model=False,
        )

        jobs = (
            MediaConversionJob.objects
            .filter(
                content_type=content_type,
                object_id__in=composition_ids,
                field_name=JOURNEY_WORKFLOW_FIELD,
                status__in=[
                    MediaJobStatus.QUEUED,
                    MediaJobStatus.PROCESSING,
                    MediaJobStatus.FAILED,
                    MediaJobStatus.CANCELED,
                ],
            )
            .select_related("content_type")
            .order_by("-updated_at")[:20]
        )

        return Response(
            MediaConversionJobSerializer(
                jobs,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path=r"processing-jobs/(?P<job_id>[0-9]+)",
    )
    def processing_job(
        self,
        request,
        job_id=None,
    ):
        """
        Return one owner-scoped Journey workflow job.

        Content Safety failures are re-exposed using TownLIT's
        normal structured API error envelope so all clients use
        the same error contract for synchronous and asynchronous
        moderation.
        """

        try:
            normalized_job_id = int(
                job_id
            )
        except (
            TypeError,
            ValueError,
        ):
            raise NotFound(
                "Journey processing job not found."
            )

        composition_ids = (
            CreativeComposition.objects
            .filter(
                owner=request.user,
                is_active=True,
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

        content_type = (
            ContentType.objects.get_for_model(
                CreativeComposition,
                for_concrete_model=False,
            )
        )

        job = (
            MediaConversionJob.objects
            .filter(
                pk=normalized_job_id,
                content_type=content_type,
                object_id__in=composition_ids,
                field_name=JOURNEY_WORKFLOW_FIELD,
            )
            .first()
        )

        if job is None:
            raise NotFound(
                "Journey processing job not found."
            )

        payload = (
            job.payload
            if isinstance(
                job.payload,
                dict,
            )
            else {}
        )

        failure = payload.get(
            "content_safety_failure"
        )

        if (
            job.status == MediaJobStatus.FAILED
            and isinstance(
                failure,
                dict,
            )
        ):
            code = str(
                failure.get(
                    "code"
                )
                or ""
            ).strip()

            if code.startswith(
                "content_safety_"
            ):
                retryable_value = failure.get(
                    "retryable",
                    False,
                )

                retryable = (
                    retryable_value is True
                    or str(
                        retryable_value
                    )
                    .strip()
                    .lower()
                    in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    }
                )

                decision = str(
                    failure.get(
                        "decision"
                    )
                    or (
                        "review"
                        if retryable
                        else "block"
                    )
                ).strip()

                reason_code = str(
                    failure.get(
                        "reason_code"
                    )
                    or (
                        "provider_unavailable"
                        if retryable
                        else "provider_flagged"
                    )
                ).strip()

                return Response(
                    {
                        "message": "Request failed.",
                        "error": {
                            "code": code,
                            "decision": decision,
                            "reason_code": reason_code,
                            "retryable": retryable,
                        },
                    },
                    status=(
                        status.HTTP_503_SERVICE_UNAVAILABLE
                        if retryable
                        else status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                )

        return Response(
            MediaConversionJobSerializer(
                job,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_200_OK,
        )
        

class JourneyViewerPagination(ConfigurablePagination):
    page_size = 30
    max_page_size = 100

class JourneyEntryViewSet(
    OwnerGateMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Individual Journey entry endpoints.
    """

    serializer_class = JourneyEntrySerializer
    permission_classes = [AllowAny]
    pagination_class = JourneyViewerPagination
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in {
            "destroy",
            "record_view",
            "analytics",
            "viewers",
        }:
            return [IsAuthenticated()]

        return super().get_permissions()

    def get_queryset(self):
        queryset = (
            JourneyEntry.objects.select_related(
                "journey",
                "content_type",
                "composition",
                "render_job",
                "music_track",
                "music_variant",
                "music_track__catalog",
                "music_track__rights",
            )
            .prefetch_related(
                "music_track__contributor_links__contributor",
            )
            .order_by("-published_at", "-id")
        )

        if (
            not self.request.user
            or not self.request.user.is_authenticated
        ):
            return queryset

        return BoundaryVisibilityQuery.exclude_boundary_conflicts(
            queryset,
            viewer=self.request.user,
        )

    @staticmethod
    def _is_owner(
        *,
        request,
        entry: JourneyEntry,
    ) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        owner = resolve_owner_from_request(request)

        if owner is None:
            return False

        owner_ct = ContentType.objects.get_for_model(
            owner.__class__,
            for_concrete_model=False,
        )

        return bool(
            entry.content_type_id == owner_ct.pk
            and entry.object_id == owner.pk
        )

    def retrieve(
        self,
        request,
        *args,
        **kwargs,
    ):
        entry = self.get_object()

        self.apply_hard_owner_gate(
            request,
            entry,
        )

        is_owner = self._is_owner(
            request=request,
            entry=entry,
        )

        now = timezone.now()

        if not is_owner:
            if entry.archived_at is not None:
                raise NotFound(
                    "Journey entry not found."
                )

            if entry.published_at > now:
                raise NotFound(
                    "Journey entry not found."
                )

            if entry.expires_at <= now:
                raise NotFound(
                    "Journey entry not found."
                )

        if not VisibilityPolicy.can_view(
            viewer=request.user,
            obj=entry,
        ):
            raise NotFound(
                "Journey entry not found."
            )

        return Response(
            self.get_serializer(entry).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="view",
    )
    def record_view(
        self,
        request,
        slug=None,
    ):
        entry = self.get_object()

        self.apply_hard_owner_gate(
            request,
            entry,
        )

        is_owner = self._is_owner(
            request=request,
            entry=entry,
        )

        # Owner views do not count.
        if is_owner:
            return Response(
                {
                    "accepted": True,
                    "created": False,
                    "ignored_owner_view": True,
                },
                status=status.HTTP_200_OK,
            )

        serializer = JourneyViewWriteSerializer(
            data=request.data,
            context={
                "request": request,
                "entry": entry,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        source = serializer.validated_data["source"]
        now = timezone.now()

        # Basic availability.
        if (
            not entry.is_active
            or entry.is_hidden
            or entry.is_suspended
            or entry.published_at > now
        ):
            raise NotFound(
                "Journey entry not found."
            )

        is_profile_archive_view = (
            source == JourneyViewSource.PROFILE_ARCHIVE
        )

        # Live surfaces require a live Entry.
        if not is_profile_archive_view:
            if (
                entry.archived_at is not None
                or entry.expires_at <= now
            ):
                raise NotFound(
                    "Journey entry not found."
                )

        if not VisibilityPolicy.can_view(
            viewer=request.user,
            obj=entry,
        ):
            raise NotFound(
                "Journey entry not found."
            )

        result = serializer.save()

        return Response(
            {
                "accepted": True,
                "created": result.created,
                "ignored_owner_view":
                    result.ignored_owner_view,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="analytics",
    )
    def analytics(
        self,
        request,
        slug=None,
    ):
        entry = self.get_object()

        self.apply_hard_owner_gate(
            request,
            entry,
        )

        if not self._is_owner(
            request=request,
            entry=entry,
        ):
            raise PermissionDenied(
                "Journey analytics are owner-only."
            )

        viewers = entry.viewer_records.all()

        metrics = viewers.aggregate(
            returning_viewers=Count(
                "id",
                filter=Q(view_count__gt=1),
            ),
            completed_viewers=Count(
                "id",
                filter=Q(completed=True),
            ),
            average_max_progress_ms=Avg(
                "max_progress_ms"
            ),
        )

        unique_viewers = int(
            entry.unique_viewers_count or 0
        )

        completed_viewers = int(
            metrics["completed_viewers"] or 0
        )

        completion_rate = (
            completed_viewers / unique_viewers
            if unique_viewers > 0
            else 0.0
        )

        source_breakdown = list(
            viewers.values("source")
            .annotate(
                viewers=Count("id")
            )
            .order_by(
                "-viewers",
                "source",
            )
        )

        payload = {
            "entry_id": entry.pk,
            "total_views": int(
                entry.view_count_internal or 0
            ),
            "unique_viewers": unique_viewers,
            "returning_viewers": int(
                metrics["returning_viewers"] or 0
            ),
            "completed_viewers": completed_viewers,
            "completion_rate": completion_rate,
            "average_max_progress_ms": float(
                metrics["average_max_progress_ms"] or 0
            ),
            "viewer_source_breakdown":
                source_breakdown,
            "reactions_count": int(
                entry.reactions_count or 0
            ),
            "reactions_breakdown":
                entry.reactions_breakdown or {},
        }

        serializer = JourneyAnalyticsSerializer(
            instance=payload
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="viewers",
    )
    def viewers(
        self,
        request,
        slug=None,
    ):
        entry = self.get_object()

        self.apply_hard_owner_gate(
            request,
            entry,
        )

        if not self._is_owner(
            request=request,
            entry=entry,
        ):
            raise PermissionDenied(
                "Journey viewers are owner-only."
            )

        queryset = (
            entry.viewer_records
            .select_related(
                "viewer",
                "viewer__label",
                "viewer__member_profile",
                "viewer__identity_verification",
            )
            .prefetch_related(
                "viewer__identity_grants",
            )
            .order_by(
                "-last_viewed_at",
                "-id",
            )
        )

        page = self.paginate_queryset(
            queryset
        )

        if page is not None:
            serializer = JourneyViewerSerializer(
                page,
                many=True,
                context={"request": request},
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = JourneyViewerSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def destroy(
        self,
        request,
        *args,
        **kwargs,
    ):
        entry = self.get_object()

        if not self._is_owner(
            request=request,
            entry=entry,
        ):
            raise PermissionDenied(
                "You do not own this Journey entry."
            )

        entry_id = entry.pk
        journey_id = entry.journey_id

        with transaction.atomic():
            locked_entry = (
                JourneyEntry.objects
                .select_for_update()
                .select_related("journey")
                .filter(pk=entry_id)
                .first()
            )

            if locked_entry is None:
                raise NotFound(
                    "Journey entry not found."
                )

            if not self._is_owner(
                request=request,
                entry=locked_entry,
            ):
                raise PermissionDenied(
                    "You do not own this Journey entry."
                )

            locked_entry.delete()

            has_remaining_entries = (
                JourneyEntry.objects
                .filter(journey_id=journey_id)
                .exists()
            )

            if not has_remaining_entries:
                Journey.objects.filter(
                    pk=journey_id,
                ).delete()

        logger.info(
            (
                "journey.entry.deleted "
                "user_id=%s "
                "entry_id=%s "
                "journey_id=%s "
                "removed_empty_journey=%s"
            ),
            getattr(request.user, "pk", None),
            entry_id,
            journey_id,
            not has_remaining_entries,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )