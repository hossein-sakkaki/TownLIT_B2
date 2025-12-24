# apps/sanctuary/views.py
from __future__ import annotations
from django.db import transaction, IntegrityError
from django.utils import timezone

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import PermissionDenied

from apps.sanctuary.models import (
    SanctuaryRequest,
    SanctuaryReview,
    SanctuaryOutcome,
    SanctuaryProtectionLabel,
    SanctuaryParticipantProfile, 
)

from apps.sanctuary.serializers import (
    SanctuaryRequestSerializer,
    SanctuaryReviewSerializer,
    SanctuaryOutcomeSerializer,
    SanctuaryParticipationStatusSerializer,
    SanctuaryOptInSerializer,
    SanctuaryCounterSerializer
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
        if getattr(user, "is_staff", False):
            return qs
        return qs.filter(requester=user)

    def perform_create(self, serializer):
        # NOTE: Keep ViewSet thin; orchestration happens in signals (after_commit).
        serializer.save(requester=self.request.user)

    @action(detail=False, methods=["get"], url_path="counter", permission_classes=[IsAuthenticated])
    def counter(self, request):
        """
        Returns sanctuary counter for a given target.
        """

        request_type = request.query_params.get("request_type")
        content_type = request.query_params.get("content_type")
        object_id = request.query_params.get("object_id")

        if not all([request_type, content_type, object_id]):
            return Response(
                {"detail": "Missing required query params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = get_sanctuary_counter(
                user=request.user,
                request_type=request_type,
                content_type_str=content_type,
                object_id=int(object_id),
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SanctuaryCounterSerializer(data)
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
        if getattr(user, "is_staff", False):
            return qs
        return qs.filter(reviewer=user)

    def perform_update(self, serializer):
        user = self.request.user

        # Atomic vote submission to prevent race conditions
        with transaction.atomic():
            locked = SanctuaryReview.objects.select_for_update().get(pk=serializer.instance.pk)

            # Slot might be replaced/inactive
            if hasattr(locked, "is_active") and locked.is_active is False:
                raise PermissionDenied("This review slot is no longer active.")

            # Reviewer-only (no staff override)
            if locked.reviewer_id != user.id:
                raise PermissionDenied("You can only vote on your own review.")

            # Vote must be a one-time action
            if locked.review_status != NO_OPINION:
                raise PermissionDenied("Vote already submitted and cannot be edited.")

            # Ensure serializer saves the locked instance
            serializer.instance = locked
            serializer.save()

            
# Sanctuary Outcome ViewSet ----------------------------------------------------------------
class SanctuaryOutcomeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SanctuaryOutcomeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SanctuaryOutcome.objects.all().order_by("-created_at")
        user = self.request.user

        if getattr(user, "is_staff", False):
            return qs

        # Safe ORM filter: only outcomes linked to requests made by this user
        # (Owners/admins of target can still access via direct retrieve if you want — see retrieve override below.)
        return qs.filter(sanctuary_requests__requester=user).distinct()

    def retrieve(self, request, *args, **kwargs):
        """
        Optional but recommended:
        Allow target owners/admins to access the outcome detail via direct link,
        even if they weren't the requester.
        """
        outcome = self.get_object()
        try:
            assert_can_appeal(outcome, request.user)  # requester OR target owner/admin OR staff
        except Exception:
            raise PermissionDenied("You are not allowed to view this Sanctuary outcome.")
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def appeal(self, request, pk=None):
        outcome = self.get_object()

        # Permission: requester OR target owner/admin
        assert_can_appeal(outcome, request.user)

        if outcome.is_appealed:
            return Response({"detail": "Already appealed."}, status=status.HTTP_400_BAD_REQUEST)

        if outcome.appeal_deadline and timezone.now() > outcome.appeal_deadline:
            return Response({"detail": "Appeal deadline passed."}, status=status.HTTP_400_BAD_REQUEST)

        outcome.is_appealed = True
        outcome.appeal_message = (request.data.get("appeal_message") or "").strip()
        outcome.save(update_fields=["is_appealed", "appeal_message"])

        # NOTE: admin assignment is done by SanctuaryOutcome post_save signal.
        return Response({"detail": "Appeal submitted."}, status=status.HTTP_200_OK)
    

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
        permission_classes=[IsAdminUser],
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

        # Sort newest-first by best available timestamp
        def _ts(x):
            return (
                x.get("created_at")
                or x.get("finalized_at")
                or x.get("applied_at")
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
    # POST /sanctuary/participation/opt-out/
    # ----------------------------    @action(detail=False, methods=["post"], url_path="opt-out")
    @action(detail=False, methods=["get"])
    def participation_status(self, request):
        data = get_participation_status(request.user)
        return Response(data)


    @action(detail=False, methods=["post"], url_path="opt-out")
    def opt_out(self, request):
        user_opt_out(request.user)
        return Response(
            get_participation_status(request.user),
            status=status.HTTP_200_OK,
        )