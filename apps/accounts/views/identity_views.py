# apps/accounts/views/identity_views.py

from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.constants.identity_verification import (
    IV_METHOD_PROVIDER,
    IV_STATUS_PENDING,
    IV_STATUS_VERIFIED,
)
from apps.accounts.constants.identity_audit import (
    IA_REVOKE,
    IA_SOURCE_ADMIN,
)
from apps.accounts.constants.trust_weights import VERIFICATION_THRESHOLD

from apps.accounts.models.identity import IdentityVerification
from apps.accounts.permissions import IsAdminUserStrict
from apps.accounts.serializers.identity_serializers import (
    IdentityStartSerializer,
    IdentityStatusSerializer,
    IdentityRevokeSerializer,
)

from apps.accounts.services.identity_audit import log_identity_event
from apps.accounts.services.identity_finalize import (
    finalize_provider_identity_approved,
    finalize_provider_identity_rejected,
)
from apps.accounts.services.identity_profile import (
    get_missing_identity_profile_fields,
)
from apps.accounts.services.identity_guard import enforce_identity_rate_limits
from apps.accounts.services.identity_provider import get_identity_provider

import logging

logger = logging.getLogger(__name__)


class IdentityViewSet(viewsets.ViewSet):
    """
    Identity verification endpoints.
    - Eligibility check
    - Provider start
    - Status
    - Admin revoke
    - Provider webhook
    """

    def _get_provider(self):
        return get_identity_provider()

    def _reconcile_existing_provider_session(self, iv):
        """
        Reconcile local pending/processing row with provider truth.
        """

        if not iv.provider_reference:
            finalize_provider_identity_rejected(
                iv=iv,
                reason="Previous verification session had no provider reference.",
                provider_payload={"local_recovery": True},
                risk_labels=[],
            )
            return "released"

        provider = self._get_provider()

        try:
            remote = provider.retrieve_session(iv.provider_reference)
        except Exception as exc:
            logger.warning(
                "[IdentityStart] Could not reconcile session user_id=%s iv_id=%s provider_reference=%s error=%s",
                iv.user_id,
                iv.id,
                iv.provider_reference,
                exc,
            )
            return "active"

        remote_status = (remote or {}).get("status")
        remote_raw = (remote or {}).get("raw") or remote
        remote_reason = (remote or {}).get("reason") or "Verification failed"
        remote_risk = (remote or {}).get("risk") or []

        logger.info(
            "[IdentityStart] Reconcile session user_id=%s iv_id=%s local_status=%s remote_status=%s provider_reference=%s",
            iv.user_id,
            iv.id,
            iv.status,
            remote_status,
            iv.provider_reference,
        )

        if remote_status == "verified":
            finalize_provider_identity_approved(
                iv=iv,
                provider_payload=remote_raw,
                risk_labels=remote_risk,
            )
            return "verified"

        if remote_status in ("canceled", "requires_input", "not_found"):
            finalize_provider_identity_rejected(
                iv=iv,
                reason=remote_reason,
                provider_payload=remote_raw,
                risk_labels=remote_risk,
            )
            return "released"

        if remote_status in ("processing", "pending"):
            return "active"

        finalize_provider_identity_rejected(
            iv=iv,
            reason=f"Previous verification session ended in unexpected state: {remote_status}",
            provider_payload=remote_raw,
            risk_labels=remote_risk,
        )
        return "released"
    
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def eligibility(self, request):
        """
        Return verification eligibility state.
        """

        trust_score = request.user.trust_score_value
        threshold = VERIFICATION_THRESHOLD
        missing_fields = get_missing_identity_profile_fields(request.user)

        score_eligible = request.user.is_verification_eligible
        profile_ready = len(missing_fields) == 0

        return Response(
            {
                "trust_score": trust_score,
                "eligible_for_verification": score_eligible and profile_ready,
                "score_eligible_for_verification": score_eligible,
                "profile_ready_for_verification": profile_ready,
                "missing_fields": missing_fields,
                "already_verified": request.user.is_verified_identity,
                "threshold": threshold,
                "remaining_score": max(threshold - trust_score, 0),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def start(self, request):
        """
        Start identity verification session using configured provider.
        """

        logger.info(
            "[IdentityStart] Start requested user_id=%s email=%s",
            request.user.id,
            request.user.email,
        )

        serializer = IdentityStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success_url = serializer.validated_data.get("success_url")
        failure_url = serializer.validated_data.get("failure_url")

        logger.info(
            "[IdentityStart] Payload validated user_id=%s success_url=%s failure_url=%s",
            request.user.id,
            success_url,
            failure_url,
        )

        # Block already verified users
        if request.user.is_verified_identity:
            raise ValidationError({"detail": "Identity is already verified."})

        # Anti-abuse protection
        enforce_identity_rate_limits(request.user)

        # Check trust eligibility
        if not request.user.is_verification_eligible:
            raise ValidationError(
                {"detail": "You are not yet eligible for identity verification."}
            )

        # Check profile completeness
        missing_fields = get_missing_identity_profile_fields(request.user)

        if missing_fields:
            raise ValidationError(
                {
                    "detail": "Complete required profile fields before identity verification.",
                    "missing_fields": missing_fields,
                }
            )

        # Load or create verification record
        iv, created = IdentityVerification.objects.get_or_create(
            user=request.user,
            defaults={
                "method": IV_METHOD_PROVIDER,
                "level": "basic",
                "status": "not_started",
            },
        )

        logger.info(
            "[IdentityStart] IV loaded user_id=%s iv_id=%s created=%s status=%s",
            request.user.id,
            iv.id,
            created,
            iv.status,
        )

        # If local row says pending/processing, reconcile with provider truth first
        if not created and iv.status in ["pending", "processing"]:
            reconcile_result = self._reconcile_existing_provider_session(iv)
            iv.refresh_from_db()

            if reconcile_result == "verified":
                return Response(
                    {"detail": "Identity already verified."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if reconcile_result == "active":
                raise ValidationError(
                    {"detail": "Verification already in progress."}
                )

            # If released, continue and create a fresh provider session on the SAME row

        # Prevent duplicate verified state
        if not created and iv.status == IV_STATUS_VERIFIED:
            return Response(
                {"detail": "Identity already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = self._get_provider()

        try:
            session = provider.create_session(
                user=request.user,
                success_url=success_url,
                failure_url=failure_url,
            )

        except Exception as exc:
            logger.exception(
                "[IdentityStart] Failed to create provider session user_id=%s error=%s",
                request.user.id,
                exc,
            )

            return Response(
                {"detail": "Failed to start identity verification session."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        verification_data = session.get("verification")
        verification_id = verification_data.get("id") if verification_data else None
        verification_url = verification_data.get("url") if verification_data else None

        if not verification_id or not verification_url:
            logger.error(
                "[IdentityStart] Invalid provider response user_id=%s session=%s",
                request.user.id,
                session,
            )

            return Response(
                {"detail": "Verification provider returned invalid response."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Reuse the SAME row for a fresh attempt
        iv.method = IV_METHOD_PROVIDER
        iv.status = IV_STATUS_PENDING
        iv.provider_reference = verification_id
        iv.provider_payload = {"session": session}
        iv.verified_at = None
        iv.rejected_at = None
        iv.revoked_at = None

        iv.save(
            update_fields=[
                "method",
                "status",
                "provider_reference",
                "provider_payload",
                "verified_at",
                "rejected_at",
                "revoked_at",
                "updated_at",
            ]
        )

        logger.info(
            "[IdentityStart] Session stored user_id=%s iv_id=%s provider_reference=%s",
            request.user.id,
            iv.id,
            verification_id,
        )

        return Response(
            {
                "verification_url": verification_url,
                "status": iv.status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def status(self, request):
        """
        Return current identity verification status.
        """

        iv = IdentityVerification.objects.filter(user=request.user).first()

        if not iv:
            return Response(
                {
                    "method": None,
                    "status": "not_started",
                    "level": "basic",
                    "verified_at": None,
                    "revoked_at": None,
                    "rejected_at": None,
                    "risk_flag": False,
                    "is_verified_identity": request.user.is_verified_identity,
                    "eligible_for_verification": request.user.is_verification_eligible,
                    "trust_score": request.user.trust_score_value,
                }
            )

        data = IdentityStatusSerializer(iv).data

        data["is_verified_identity"] = request.user.is_verified_identity
        data["eligible_for_verification"] = request.user.is_verification_eligible
        data["trust_score"] = request.user.trust_score_value

        return Response(data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsAdminUserStrict],
        url_path="revoke",
    )
    def revoke(self, request, pk=None):
        """
        Admin revoke identity verification.
        """

        serializer = IdentityRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        iv = get_object_or_404(IdentityVerification, user_id=pk)

        previous_status = iv.status

        iv.status = "revoked"
        iv.revoked_at = timezone.now()
        iv.notes = serializer.validated_data.get("reason", "Admin revoke")
        iv.method = "admin"

        iv.save(update_fields=["status", "revoked_at", "notes", "method", "updated_at"])

        active_grant = iv.user.identity_grants.filter(is_active=True).first()

        if active_grant:
            active_grant.revoke()

        log_identity_event(
            user=iv.user,
            identity_verification=iv,
            action=IA_REVOKE,
            source=IA_SOURCE_ADMIN,
            actor=request.user,
            previous_status=previous_status,
            new_status=iv.status,
            reason=iv.notes,
        )

        return Response({"detail": "Identity revoked by admin."})

    @action(
        detail=False,
        methods=["post"],
        authentication_classes=[],
        permission_classes=[],
        url_path="webhook/provider",
    )
    def provider_webhook(self, request):
        """
        Handle identity provider webhook.
        """

        provider = self._get_provider()

        signature = (
            request.headers.get("Stripe-Signature")
            or request.META.get("HTTP_STRIPE_SIGNATURE")
        )

        logger.info(
            "[StripeWebhook] Received event signature=%s",
            signature,
        )

        event = provider.verify_webhook(request.body, signature)

        if not event:
            return Response(
                {"detail": "Invalid signature"},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = provider.parse_webhook(event)

        session_id = data.get("session_id")

        if not session_id:
            return Response(
                {"detail": "Missing session id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        iv = get_object_or_404(
            IdentityVerification,
            provider_reference=session_id,
        )

        status_value = data.get("status")

        if status_value == "verified":
            finalize_provider_identity_approved(
                iv=iv,
                provider_payload=data.get("raw"),
                risk_labels=data.get("risk") or [],
            )

        elif status_value in ("canceled", "requires_input"):
            finalize_provider_identity_rejected(
                iv=iv,
                reason=data.get("reason") or "Verification failed",
                provider_payload=data.get("raw"),
                risk_labels=data.get("risk") or [],
            )

        return Response({"ok": True}, status=status.HTTP_200_OK)