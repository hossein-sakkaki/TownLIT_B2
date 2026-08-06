# apps/sanctuary/views.py
from __future__ import annotations
from django.db import transaction, IntegrityError
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts.permissions import IsAdminUserStrict, is_platform_admin

from apps.sanctuary.models import (
    SanctuaryOutcome,
    SanctuaryParticipantProfile,
    SanctuaryProtectionLabel,
    SanctuaryRequest,
    SanctuaryReview,
    SanctuarySafetyHold,
)

from apps.sanctuary.serializers import (
    SanctuaryRequestSerializer,
    SanctuaryReviewSerializer,
    SanctuaryOutcomeSerializer,
    SanctuaryParticipationStatusSerializer,
    SanctuaryOptInSerializer,
    SanctuaryCounterSerializer,
    SanctuaryTargetStatusSerializer,
)
from apps.sanctuary.constants.target_models import (
    content_type_key,
    is_allowed_target_model,
)
from apps.sanctuary.services.safety_hold_status import (
    get_sanctuary_target_status,
)
from apps.sanctuary.realtime.utils import (
    normalize_content_type,
    sanitize_group_part,
)
from apps.sanctuary.services.target_access import (
    assert_sanctuary_target_access,
    resolve_content_type_key,
)

from apps.sanctuary.constants.states import NO_OPINION
from apps.main.constants import SANCTUARY_COUNCIL_RULES
from apps.sanctuary.constants.reasons import REASON_MAP
from apps.sanctuary.services.appeal_access import assert_can_appeal
from apps.sanctuary.services.participation_status import get_participation_status
from apps.sanctuary.services.participants import user_opt_in, user_opt_out, get_or_create_profile
from apps.sanctuary.services.counter import get_sanctuary_counter

from apps.profiles.models import Member
from apps.main.models import TermsAndPolicy, UserAgreement
import logging

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Sanctuary Realtime helpers
# -----------------------------------------------------------------------------
def _sanctuary_request_group_name(request_id: int) -> str:
    return f"sanctuary.request.{int(request_id)}"


def _sanctuary_target_group_name(
    request_type: str,
    content_type: str,
    object_id: int,
) -> str:
    rt = sanitize_group_part(request_type)
    ct = sanitize_group_part(normalize_content_type(content_type))
    return f"sanctuary.target.{rt}.{ct}.{int(object_id)}"


def _safe_sanctuary_broadcast(
    group_name: str,
    event_name: str,
    payload: dict,
):
    """
    Safe WS send for Sanctuary.
    Never breaks HTTP flow if Redis / Channels is unavailable.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not configured; skip sanctuary WS send.")
            return

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "dispatch_event",
                "app": "sanctuary",
                "event": event_name,
                "data": payload,
            },
        )
    except Exception:
        logger.exception("Sanctuary WS broadcast failed ignored.")


def _safe_sanctuary_global_broadcast(
    event_name: str,
    payload: dict,
):
    _safe_sanctuary_broadcast(
        "sanctuary_global",
        event_name,
        payload,
    )


def _content_type_key(
    content_type,
) -> str:
    if not content_type:
        return ""

    app_label = getattr(
        content_type,
        "app_label",
        None,
    )

    model = getattr(
        content_type,
        "model",
        None,
    )

    if app_label and model:
        return (
            f"{str(app_label).lower()}."
            f"{str(model).lower()}"
        )

    return str(
        content_type
    ).strip().lower()


def _counter_payload_for_request(
    *,
    request_obj: SanctuaryRequest,
    user,
    expose_internal_counts: bool = False,
) -> dict:
    """
    Build a counter payload.

    Shared target broadcasts must always call this with:
        expose_internal_counts=False
    """
    content_type_key_value = (
        _content_type_key(
            request_obj.content_type
        )
    )

    try:
        counter = get_sanctuary_counter(
            user=user,
            request_type=(
                request_obj.request_type
            ),
            content_type_str=(
                content_type_key_value
            ),
            object_id=int(
                request_obj.object_id
            ),
            expose_internal_counts=(
                expose_internal_counts
            ),
        )

        return {
            "request_type": counter.get(
                "request_type",
                request_obj.request_type,
            ),
            "content_type": counter.get(
                "content_type",
                content_type_key_value,
            ),
            "object_id": int(
                counter.get(
                    "object_id",
                    request_obj.object_id,
                )
            ),
            "count": int(
                counter.get(
                    "count",
                    0,
                )
            ),
            "threshold": int(
                counter.get(
                    "threshold",
                    0,
                )
            ),
            "has_reported": bool(
                counter.get(
                    "has_reported",
                    False,
                )
            ),
            "request_id": (
                counter.get(
                    "request_id"
                )
            ),
        }

    except Exception:
        logger.exception(
            "Failed to build Sanctuary counter payload."
        )

        return {
            "request_type": (
                request_obj.request_type
            ),
            "content_type": (
                content_type_key_value
            ),
            "object_id": int(
                request_obj.object_id
            ),
            "count": 0,
            "threshold": 0,
            "has_reported": False,
            "request_id": None,
        }


def _broadcast_sanctuary_counter_updated(
    *,
    request_obj: SanctuaryRequest,
    user,
):
    """
    Broadcast only a privacy-safe invalidation payload.

    The target group may contain multiple visitors, so it must never
    receive aggregate counts, threshold values, requester state, or
    request IDs belonging to another user.
    """
    content_type_key_value = (
        _content_type_key(
            request_obj.content_type
        )
    )

    payload = {
        "request_type": (
            request_obj.request_type
        ),
        "content_type": (
            content_type_key_value
        ),
        "object_id": int(
            request_obj.object_id
        ),
        "count": 0,
        "threshold": 0,
        "has_reported": False,
        "request_id": None,
        "refresh_required": True,
    }

    _safe_sanctuary_broadcast(
        _sanctuary_target_group_name(
            request_obj.request_type,
            content_type_key_value,
            request_obj.object_id,
        ),
        "counter_updated",
        payload,
    )


def _request_event_payload(
    request_obj: SanctuaryRequest,
    event_name: str,
    extra: dict | None = None,
) -> dict:
    content_type_key = _content_type_key(request_obj.content_type)

    payload = {
        "event": event_name,
        "request_id": request_obj.id,
        "request_type": request_obj.request_type,
        "status": request_obj.status,
        "resolution_mode": request_obj.resolution_mode,
        "content_type": content_type_key,
        "object_id": int(request_obj.object_id),
        "report_count_snapshot": int(request_obj.report_count_snapshot or 0),
        "updated_at": request_obj.updated_at.isoformat() if request_obj.updated_at else None,
    }

    if extra:
        payload.update(extra)

    return payload


def _broadcast_sanctuary_request_event(
    *,
    request_obj: SanctuaryRequest,
    event_name: str,
    extra: dict | None = None,
    include_request_group: bool = True,
    include_global: bool = True,
):
    payload = _request_event_payload(
        request_obj,
        event_name,
        extra=extra,
    )

    if include_request_group:
        _safe_sanctuary_broadcast(
            _sanctuary_request_group_name(request_obj.id),
            event_name,
            payload,
        )

    if include_global:
        _safe_sanctuary_global_broadcast(
            event_name,
            payload,
        )
        
# Sanctuary Request ViewSet ----------------------------------------------------------------
class SanctuaryRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    - Users can create requests.
    - Users can see ONLY their own requests.
    - Staff can see all.
    - No update / no delete (workflow is system-driven).
    """
    serializer_class = SanctuaryRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SanctuaryRequest.objects.all().order_by("-created_at")
        user = self.request.user

        if is_platform_admin(user):
            return qs

        return qs.filter(requester=user)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                request_obj = serializer.save(requester=self.request.user)
        except IntegrityError as exc:
            constraint_name = getattr(
                getattr(exc, "__cause__", None),
                "diag",
                None,
            )
            constraint_name = getattr(constraint_name, "constraint_name", None)

            if constraint_name == "uniq_open_sanctuary_request_per_user_target":
                raise serializers.ValidationError({
                    "detail": "You already have an active Sanctuary request for this target.",
                    "code": "active_sanctuary_request_already_exists",
                })

            raise

        transaction.on_commit(lambda: _broadcast_sanctuary_counter_updated(
            request_obj=request_obj,
            user=self.request.user,
        ))

        transaction.on_commit(lambda: _broadcast_sanctuary_request_event(
            request_obj=request_obj,
            event_name="request_created",
            extra={
                "requester_id": self.request.user.id,
                "created_at": request_obj.created_at.isoformat() if request_obj.created_at else None,
            },
            include_request_group=True,
            include_global=True,
        ))

    @action(
        detail=False,
        methods=["get"],
        url_path="counter",
        permission_classes=[IsAuthenticated],
    )
    def counter(self, request):
        """
        Return privacy-safe Sanctuary state for one target.

        Aggregate counts are visible only to:
        - staff
        - target account/content owner
        - organization owner or approved admin
        - Messenger group founder or elder
        """

        request_type = str(
            request.query_params.get(
                "request_type"
            )
            or ""
        ).strip()

        content_type_value = str(
            request.query_params.get(
                "content_type"
            )
            or ""
        ).strip()

        object_id_value = (
            request.query_params.get(
                "object_id"
            )
        )

        if (
            not request_type
            or not content_type_value
            or object_id_value in (
                None,
                "",
            )
        ):
            return Response(
                {
                    "detail": (
                        "request_type, content_type, "
                        "and object_id are required."
                    ),
                    "code": (
                        "missing_target_parameters"
                    ),
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        try:
            object_id = int(
                object_id_value
            )
        except (
            TypeError,
            ValueError,
        ):
            return Response(
                {
                    "detail": (
                        "object_id must be a positive "
                        "integer."
                    ),
                    "code": (
                        "invalid_target_object_id"
                    ),
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        if object_id < 1:
            return Response(
                {
                    "detail": (
                        "object_id must be a positive "
                        "integer."
                    ),
                    "code": (
                        "invalid_target_object_id"
                    ),
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        try:
            content_type = (
                resolve_content_type_key(
                    content_type_value
                )
            )

            access = (
                assert_sanctuary_target_access(
                    user=request.user,
                    request_type=request_type,
                    content_type=content_type,
                    object_id=object_id,
                    allow_self_target=True,
                )
            )

            expose_internal_counts = bool(
                is_platform_admin(request.user)
                or access.is_owner
            )

            data = get_sanctuary_counter(
                user=request.user,
                request_type=request_type,
                content_type_str=(
                    content_type_key(
                        content_type
                    )
                ),
                object_id=object_id,
                expose_internal_counts=(
                    expose_internal_counts
                ),
            )

        except serializers.ValidationError as exc:
            return Response(
                exc.detail,
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(
                        exc
                    ),
                    "code": (
                        "invalid_sanctuary_counter_request"
                    ),
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        serializer = SanctuaryCounterSerializer(
            data
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


    @action(
        detail=False,
        methods=["get"],
        url_path="target-status",
        permission_classes=[IsAuthenticated],
    )
    def target_status(self, request):
        request_type = str(request.query_params.get("request_type") or "").strip()
        content_type_value = str(request.query_params.get("content_type") or "").strip()
        object_id_value = request.query_params.get("object_id")

        if not request_type or not content_type_value or object_id_value in (None, ""):
            return Response(
                {
                    "detail": "request_type, content_type, and object_id are required.",
                    "code": "missing_target_parameters",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            object_id = int(object_id_value)
        except (TypeError, ValueError):
            return Response(
                {
                    "detail": "object_id must be a positive integer.",
                    "code": "invalid_target_object_id",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if object_id < 1:
            return Response(
                {
                    "detail": "object_id must be a positive integer.",
                    "code": "invalid_target_object_id",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_content_type = resolve_content_type_key(content_type_value)

            if not is_allowed_target_model(
                request_type=request_type,
                content_type=target_content_type,
            ):
                return Response(
                    {
                        "detail": "This target model is not allowed for the selected request type.",
                        "code": "invalid_target_model",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            payload = get_sanctuary_target_status(
                user=request.user,
                request_type=request_type,
                content_type=target_content_type,
                object_id=object_id,
            )

        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        serializer = SanctuaryTargetStatusSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(
        detail=False,
        methods=["get"],
        url_path="reasons",
        permission_classes=[IsAuthenticated],
    )
    def reasons(self, request):
        """
        Returns allowed reasons for a given request_type
        """
        request_type = request.query_params.get("request_type")
        if not request_type:
            return Response(
                {"detail": "request_type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reasons = REASON_MAP.get(request_type)
        if not reasons:
            return Response(
                {"detail": "Invalid request_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # return as list for frontend
        return Response(
            {
                "request_type": request_type,
                "reasons": [
                    {"code": k, "label": v} for k, v in reasons.items()
                ],
            },
            status=status.HTTP_200_OK,
        )


# Sanctuary Review ViewSet ----------------------------------------------------------------
class SanctuaryReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Reviews:
    - Created by the system only (no create endpoint here)
    - Reviewer can submit ONE final vote only (no edits after)
    - Staff can view all, but cannot edit votes
    """

    serializer_class = SanctuaryReviewSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_queryset(self):
        qs = (
            SanctuaryReview.objects
            .select_related("sanctuary_request")
            .order_by("-assigned_at")
        )

        user = self.request.user

        if is_platform_admin(user):
            return qs

        return qs.filter(reviewer=user)

    def perform_update(self, serializer):
        user = self.request.user

        # Atomic vote submission to prevent race conditions
        with transaction.atomic():
            locked = (
                SanctuaryReview.objects
                .select_for_update()
                .select_related("sanctuary_request")
                .get(pk=serializer.instance.pk)
            )

            # Slot might be replaced/inactive
            if hasattr(locked, "is_active") and locked.is_active is False:
                raise PermissionDenied("This review slot is no longer active.")

            # Reviewer-only no staff override
            if locked.reviewer_id != user.id:
                raise PermissionDenied("You can only vote on your own review.")

            # Vote must be a one-time action
            if locked.review_status != NO_OPINION:
                raise PermissionDenied("Vote already submitted and cannot be edited.")

            # Ensure serializer saves the locked instance
            serializer.instance = locked
            updated_review = serializer.save()

            request_obj = updated_review.sanctuary_request

            transaction.on_commit(lambda: _broadcast_sanctuary_request_event(
                request_obj=request_obj,
                event_name="review_updated",
                extra={
                    "review_id": updated_review.id,
                    "reviewer_id": user.id,
                    "review_status": updated_review.review_status,
                    "reviewed_at": updated_review.reviewed_at.isoformat()
                    if updated_review.reviewed_at
                    else None,
                },
                include_request_group=True,
                include_global=True,
            ))
            
# Sanctuary Outcome ViewSet ----------------------------------------------------------------
class SanctuaryOutcomeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SanctuaryOutcomeSerializer
    permission_classes = [IsAuthenticated]

    def _base_queryset(self):
        return (
            SanctuaryOutcome.objects
            .select_related(
                "content_type",
                "assigned_admin",
            )
            .prefetch_related(
                "sanctuary_requests",
                "sanctuary_requests__requester",
            )
            .order_by("-created_at")
        )

    def get_queryset(self):
        qs = self._base_queryset()
        user = self.request.user

        if is_platform_admin(user):
            return qs

        return qs.filter(
            sanctuary_requests__requester=user,
        ).distinct()

    def _get_outcome_for_access_check(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)

        if lookup_value is None:
            raise NotFound("Sanctuary outcome not found.")

        try:
            outcome = self._base_queryset().get(
                **{self.lookup_field: lookup_value}
            )
        except (
            SanctuaryOutcome.DoesNotExist,
            ValueError,
            TypeError,
        ):
            raise NotFound("Sanctuary outcome not found.")

        try:
            assert_can_appeal(
                outcome,
                self.request.user,
            )
        except PermissionDenied:
            raise
        except Exception:
            logger.exception(
                "Sanctuary outcome access check failed.",
                extra={
                    "outcome_id": getattr(outcome, "pk", None),
                    "user_id": getattr(self.request.user, "pk", None),
                },
            )
            raise PermissionDenied(
                "You are not allowed to access this Sanctuary outcome."
            )

        return outcome

    def retrieve(self, request, *args, **kwargs):
        outcome = self._get_outcome_for_access_check()

        serializer = self.get_serializer(
            outcome,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="appeal",
    )
    def appeal(self, request, pk=None):
        outcome = self._get_outcome_for_access_check()

        if outcome.is_appealed:
            return Response(
                {
                    "detail": "An appeal has already been submitted.",
                    "code": "sanctuary_outcome_already_appealed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            outcome.appeal_deadline
            and timezone.now() > outcome.appeal_deadline
        ):
            return Response(
                {
                    "detail": "The appeal deadline has passed.",
                    "code": "sanctuary_appeal_deadline_passed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        appeal_message = str(
            request.data.get("appeal_message") or ""
        ).strip()

        if not appeal_message:
            return Response(
                {
                    "appeal_message": "An appeal explanation is required.",
                    "code": "sanctuary_appeal_message_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(appeal_message) > 4000:
            return Response(
                {
                    "appeal_message": "Appeal explanation cannot exceed 4000 characters.",
                    "code": "sanctuary_appeal_message_too_long",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            locked_outcome = (
                SanctuaryOutcome.objects
                .select_for_update()
                .get(pk=outcome.pk)
            )

            if locked_outcome.is_appealed:
                return Response(
                    {
                        "detail": "An appeal has already been submitted.",
                        "code": "sanctuary_outcome_already_appealed",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if (
                locked_outcome.appeal_deadline
                and timezone.now() > locked_outcome.appeal_deadline
            ):
                return Response(
                    {
                        "detail": "The appeal deadline has passed.",
                        "code": "sanctuary_appeal_deadline_passed",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            locked_outcome.is_appealed = True
            locked_outcome.appeal_message = appeal_message
            locked_outcome.save(
                update_fields=[
                    "is_appealed",
                    "appeal_message",
                ]
            )

            linked_requests = list(
                locked_outcome.sanctuary_requests.all()
            )

            for request_obj in linked_requests:
                transaction.on_commit(
                    lambda request_obj=request_obj: (
                        _broadcast_sanctuary_request_event(
                            request_obj=request_obj,
                            event_name="outcome_appealed",
                            extra={
                                "outcome_id": locked_outcome.id,
                                "is_appealed": True,
                            },
                            include_request_group=True,
                            include_global=True,
                        )
                    )
                )

        return Response(
            {
                "detail": "Appeal submitted.",
                "outcome_id": locked_outcome.id,
                "is_appealed": True,
            },
            status=status.HTTP_200_OK,
        )
    

# Sanctuary History ViewSet ----------------------------------------------------------------
class SanctuaryHistoryViewSet(viewsets.ViewSet):
    """
    Read-only history endpoints for Sanctuary.
    - /sanctuary/history/my/        (user's own requests)
    - /sanctuary/history/target/    (admin-only: requests+outcomes+labels for a target)
    """

    permission_classes = [IsAuthenticated]

    # ------------------------------------------------------------------
    # GET /sanctuary/history/my/
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="my")
    def my_history(self, request):
        """
        Return user's own Sanctuary requests history (last 200).
        """
        qs = (
            SanctuaryRequest.objects
            .filter(requester=request.user)
            .order_by("-created_at")[:200]
        )

        items = []
        for r in qs:
            items.append({
                "type": "request",
                "id": r.id,
                "request_type": r.request_type,
                "reasons": r.reasons,  # ✅ reasons (JSON list)
                "status": r.status,
                "resolution_mode": r.resolution_mode,
                "report_count_snapshot": r.report_count_snapshot,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "target": {
                    "content_type_id": r.content_type_id,
                    "object_id": r.object_id,
                },
            })

        return Response({"items": items}, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # GET /sanctuary/history/target/?content_type_id=..&object_id=..
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        url_path="target",
        permission_classes=[IsAdminUserStrict],
    )
    def target_history(self, request):
        """
        Admin-only: return history for a specific target object.
        Query params:
          - content_type_id (int)
          - object_id (int)
        """
        ct_id = request.query_params.get("content_type_id")
        obj_id = request.query_params.get("object_id")

        if not ct_id or not obj_id:
            return Response(
                {"detail": "content_type_id and object_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate ints (avoid silent wrong queries)
        try:
            ct_id_int = int(ct_id)
            obj_id_int = int(obj_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "content_type_id and object_id must be integers."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Requests
        reqs = (
            SanctuaryRequest.objects
            .filter(content_type_id=ct_id_int, object_id=obj_id_int)
            .order_by("-created_at")[:200]
        )

        # Outcomes linked to same target
        outs = (
            SanctuaryOutcome.objects
            .filter(content_type_id=ct_id_int, object_id=obj_id_int)
            .order_by("-finalized_at", "-created_at")[:200]
        )

        # Labels
        labels = (
            SanctuaryProtectionLabel.objects
            .filter(content_type_id=ct_id_int, object_id=obj_id_int)
            .order_by("-applied_at")[:200]
        )

        holds = (
            SanctuarySafetyHold.objects
            .filter(content_type_id=ct_id_int, object_id=obj_id_int)
            .order_by("-applied_at")[:200]
        )

        items = []

        for r in reqs:
            items.append({
                "type": "request",
                "id": r.id,
                "request_type": r.request_type,
                "reasons": r.reasons,  # ✅
                "status": r.status,
                "resolution_mode": r.resolution_mode,
                "report_count_snapshot": r.report_count_snapshot,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "requester_id": r.requester_id,
            })

        for o in outs:
            items.append({
                "type": "outcome",
                "id": o.id,
                "status": o.outcome_status,
                "is_appealed": o.is_appealed,
                "admin_reviewed": o.admin_reviewed,
                "appeal_deadline": o.appeal_deadline.isoformat() if o.appeal_deadline else None,
                "finalized_at": o.finalized_at.isoformat() if o.finalized_at else None,  # ✅ finalized_at
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

        for l in labels:
            items.append({
                "type": "label",
                "id": l.id,
                "label_type": l.label_type,
                "applied_by": l.applied_by,
                "is_active": l.is_active,
                "applied_at": l.applied_at.isoformat() if l.applied_at else None,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "outcome_id": l.outcome_id,   # ✅ helpful for audit linking
                "created_by_id": l.created_by_id,
            })

        for hold in holds:
            items.append({
                "type": "safety_hold",
                "id": hold.id,
                "status": hold.status,
                "request_type": hold.request_type,
                "reason_codes": hold.reason_codes,
                "trigger_request_id": hold.trigger_request_id,
                "did_deactivate_target": hold.did_deactivate_target,
                "previous_is_active": hold.previous_is_active,
                "previous_is_suspended": hold.previous_is_suspended,
                "applied_at": hold.applied_at.isoformat() if hold.applied_at else None,
                "ended_at": hold.ended_at.isoformat() if hold.ended_at else None,
                "ended_by_id": hold.ended_by_id,
                "release_note": hold.release_note,
            })
    
        # Sort newest-first by best available timestamp
        def _ts(item):
            return (
                item.get("created_at")
                or item.get("finalized_at")
                or item.get("applied_at")
                or item.get("ended_at")
                or ""
            )

        items.sort(key=_ts, reverse=True)

        return Response({"items": items}, status=status.HTTP_200_OK)
    

# Sanctuary Participation ViewSet ----------------------------------------------------------------
class SanctuaryParticipationViewSet(viewsets.ViewSet):
    """
    Settings panel backend for Sanctuary council participation.

    Endpoints:
      GET  /sanctuary/participation/            -> status + policy + gates + eligibility
      POST /sanctuary/participation/opt-in/     -> accept policy + set profile.is_participant=True (if eligible)
      POST /sanctuary/participation/opt-out/    -> set profile.is_participant=False
    """
    permission_classes = [IsAuthenticated]

    # ----------------------------
    # Helpers
    # ----------------------------
    def _get_member(self, user) -> Member:
        try:
            return user.member_profile
        except Exception:
            raise PermissionDenied("Member profile not found.")

    def _get_policy(self, lang: str):
        """
        Fetch active policy by policy_type + language.
        Falls back to 'en' if requested language not found.
        """
        lang = (lang or "en").strip().lower()

        policy = (
            TermsAndPolicy.objects
            .filter(policy_type=SANCTUARY_COUNCIL_RULES, is_active=True, language=lang)
            .order_by("-last_updated")
            .first()
        )
        if policy:
            return policy

        return (
            TermsAndPolicy.objects
            .filter(policy_type=SANCTUARY_COUNCIL_RULES, is_active=True, language="en")
            .order_by("-last_updated")
            .first()
        )

    def _agreement_status(self, user, policy):
        """
        Agreement is valid if:
        - latest UserAgreement exists for (user, policy), AND
        - latest.agreed_at >= policy.last_updated
        """
        if not policy:
            return False, None

        ua = (
            UserAgreement.objects
            .filter(user=user, policy=policy, is_latest_agreement=True)
            .order_by("-agreed_at")
            .first()
        )
        if not ua:
            return False, None

        if policy.last_updated and ua.agreed_at and ua.agreed_at < policy.last_updated:
            return False, ua.agreed_at

        return True, ua.agreed_at


    def _gates_and_reasons(self, user, member: Member, profile: SanctuaryParticipantProfile, policy):
        """
        Central gates for showing/enabling the opt-in button in UI.
        """
        reasons = []

        # Identity gate (CustomUser)
        if not bool(getattr(user, "is_verified_identity", False)):
            reasons.append("identity_not_verified")

        # TownLIT gate (Member)
        if not bool(getattr(member, "is_townlit_verified", False)):
            reasons.append("townlit_not_verified")

        # Optional: member active gate (if you rely on it)
        if hasattr(member, "is_active") and (member.is_active is False):
            reasons.append("member_inactive")

        # Sanctuary eligibility gate (admin/system controlled)
        if not bool(getattr(profile, "is_eligible", True)):
            reasons.append("sanctuary_ineligible")

        # Policy must exist to opt-in (we must record acceptance)
        if not policy:
            reasons.append("policy_missing")

        can_opt_in = (len(reasons) == 0)
        return can_opt_in, reasons

    def _ensure_policy_acceptance(self, *, user, policy):
        """
        History-friendly acceptance:
        - If latest exists and fresh -> no-op
        - Else create NEW UserAgreement row (is_latest_agreement=True)
            (model.save() will flip previous latest to False)
        """
        latest = (
            UserAgreement.objects
            .filter(user=user, policy=policy, is_latest_agreement=True)
            .order_by("-agreed_at")
            .first()
        )

        if latest and (not policy.last_updated or latest.agreed_at >= policy.last_updated):
            return latest

        try:
            return UserAgreement.objects.create(
                user=user,
                policy=policy,
                is_latest_agreement=True,
            )
        except IntegrityError:
            # Concurrent opt-in: another request created the latest row
            return (
                UserAgreement.objects
                .filter(user=user, policy=policy, is_latest_agreement=True)
                .order_by("-agreed_at")
                .first()
            )

    # ----------------------------
    # GET /sanctuary/participation/
    # ----------------------------
    def list(self, request):
        user = request.user
        member = self._get_member(user)
        profile = get_or_create_profile(user)

        lang = request.query_params.get("lang") or getattr(user, "language", None) or "en"
        policy = self._get_policy(lang)

        has_agreed, agreed_at = self._agreement_status(user, policy)
        can_opt_in, reasons = self._gates_and_reasons(user, member, profile, policy)

        payload = {
            # Gates
            "eligible": bool(can_opt_in),
            "ineligible_reasons": reasons,

            # User/Member core flags
            "is_verified_identity": bool(getattr(user, "is_verified_identity", False)),
            "is_townlit_verified": bool(getattr(member, "is_townlit_verified", False)),

            # ParticipationProfile flags
            "is_sanctuary_participant": bool(getattr(profile, "is_participant", False)),
            "is_sanctuary_eligible": bool(getattr(profile, "is_eligible", True)),
            "eligible_reason": getattr(profile, "eligible_reason", None),
            "eligible_changed_at": getattr(profile, "eligible_changed_at", None),

            # Policy
            "policy_available": bool(policy),
            "policy_id": getattr(policy, "id", None) if policy else None,
            "policy_type": getattr(policy, "policy_type", "") if policy else "",
            "policy_title": getattr(policy, "title", "") if policy else "",
            "policy_content": getattr(policy, "content", "") if policy else "",
            "policy_language": getattr(policy, "language", "") if policy else "",
            "policy_version_number": getattr(policy, "version_number", "") if policy else "",
            "policy_last_updated": getattr(policy, "last_updated", None) if policy else None,
            "requires_acceptance": bool(getattr(policy, "requires_acceptance", True)) if policy else True,

            # Agreement
            "has_agreed": bool(has_agreed),
            "agreed_at": agreed_at,
        }

        return Response(SanctuaryParticipationStatusSerializer(payload).data, status=status.HTTP_200_OK)

    # ----------------------------
    # POST /sanctuary/participation/opt-in/
    # ----------------------------
    @action(detail=False, methods=["post"], url_path="opt-in")
    def opt_in(self, request):
        user = request.user
        member = self._get_member(user)

        lang = request.query_params.get("lang") or getattr(user, "language", None) or "en"
        policy = self._get_policy(lang)

        if not policy:
            return Response(
                {"detail": "Sanctuary policy is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ✅ MUST: frontend must send policy_id the user saw
        ser = SanctuaryOptInSerializer(data=request.data)
        if not ser.is_valid():
            logger.error("Sanctuary opt-in validation failed", extra={
                "errors": ser.errors,
                "data": request.data,
            })
            return Response(ser.errors, status=400)

        ser.is_valid(raise_exception=True)
        sent_policy_id = ser.validated_data["policy_id"]

        if int(sent_policy_id) != int(policy.id):
            return Response(
                {"detail": "Policy mismatch. Refresh and accept the latest policy."},
                status=status.HTTP_409_CONFLICT
            )

        # Gates
        if not bool(getattr(user, "is_verified_identity", False)):
            return Response(
                {"detail": "Identity verification is required to join the Sanctuary council pool."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not bool(getattr(member, "is_townlit_verified", False)):
            return Response(
                {"detail": "TownLIT verification is required to join the Sanctuary council pool."},
                status=status.HTTP_403_FORBIDDEN
            )

        # NOTE: eligibility check is enforced inside user_opt_in as well
        with transaction.atomic():
            self._ensure_policy_acceptance(user=user, policy=policy)
            profile = user_opt_in(user)

        return Response(
            {"detail": "Opt-in successful.", "is_sanctuary_participant": True},
            status=status.HTTP_200_OK
        )

    # ----------------------------
    # GET /sanctuary-participation/status/
    # ----------------------------
    @action(detail=False, methods=["get"], url_path="status")
    def participation_status(self, request):
        data = get_participation_status(request.user)

        return Response(
            data,
            status=status.HTTP_200_OK,
        )

    # ----------------------------
    # POST /sanctuary-participation/opt-out/
    # ----------------------------
    @action(detail=False, methods=["post"], url_path="opt-out")
    def opt_out(self, request):
        user_opt_out(request.user)

        return Response(
            get_participation_status(request.user),
            status=status.HTTP_200_OK,
        )