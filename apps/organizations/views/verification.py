# apps/organizations/views/verification.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.constants import (
    OrganizationPermissionKey,
    OrganizationVerificationStatus,
)
from apps.organizations.models import (
    OrganizationRelationship,
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
    OrganizationVerificationGrant,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.serializers import (
    OrganizationVerificationApprovalSerializer,
    OrganizationVerificationCaseCreateSerializer,
    OrganizationVerificationCaseSerializer,
    OrganizationVerificationDocumentCreateSerializer,
    OrganizationVerificationDocumentReviewSerializer,
    OrganizationVerificationDocumentSerializer,
    OrganizationVerificationGrantSerializer,
    OrganizationVerificationReviewNoteSerializer,
    OrganizationVerificationRevokeSerializer,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.verification import (
    add_verification_document,
    approve_verification_case,
    create_verification_case,
    mark_verification_needs_information,
    reject_verification_case,
    review_verification_document,
    revoke_verification_grant,
    start_verification_review,
    submit_verification_case,
    withdraw_verification_case,
)

from .access import get_visible_organization_or_404
from .helpers import raise_drf_validation_error


def _ensure_can_view_cases(user, organization):
    if getattr(user, "is_staff", False):
        return

    if not user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_VERIFICATION,
    ):
        raise PermissionDenied(
            "You do not have permission to view organization verification cases."
        )


def _get_case(public_id):
    verification_case = (
        OrganizationVerificationCase.objects
        .select_related(
            "organization",
            "relationship__source_organization",
            "relationship__target_organization",
            "renewal_of",
        )
        .prefetch_related("documents", "grants__relationship__source_organization")
        .filter(public_id=public_id)
        .first()
    )
    if not verification_case:
        raise NotFound("Verification case not found.")
    return verification_case


class OrganizationVerificationCasesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        _ensure_can_view_cases(request.user, organization)

        queryset = (
            OrganizationVerificationCase.objects
            .select_related("relationship", "renewal_of")
            .prefetch_related("documents", "grants")
            .filter(organization=organization)
            .order_by("-created_at", "-id")
        )

        return Response(
            OrganizationVerificationCaseSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        serializer = OrganizationVerificationCaseCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        relationship_public_id = data.pop(
            "relationship_public_id",
            None,
        )
        relationship = None

        if relationship_public_id:
            relationship = OrganizationRelationship.objects.filter(
                public_id=relationship_public_id,
            ).first()
            if not relationship:
                raise NotFound("Organization relationship not found.")

        try:
            verification_case = create_verification_case(
                organization=organization,
                actor=request.user,
                relationship=relationship,
                **data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationVerificationCaseDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, public_id):
        verification_case = _get_case(public_id)
        _ensure_can_view_cases(
            request.user,
            verification_case.organization,
        )
        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data
        )


class OrganizationVerificationDocumentCreateView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        serializer = OrganizationVerificationDocumentCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            document = add_verification_document(
                verification_case=verification_case,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationDocumentSerializer(
                document,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationVerificationSubmitView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        try:
            verification_case = submit_verification_case(
                verification_case=verification_case,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data
        )


class OrganizationVerificationWithdrawView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        try:
            verification_case = withdraw_verification_case(
                verification_case=verification_case,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data
        )


class OrganizationVerificationReviewQueueView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request):
        if not getattr(request.user, "is_staff", False):
            raise PermissionDenied("Only TownLIT staff can access the verification review queue.")

        queryset = (
            OrganizationVerificationCase.objects
            .select_related("organization", "relationship", "renewal_of")
            .prefetch_related("documents")
            .filter(status__in=[
                OrganizationVerificationStatus.SUBMITTED,
                OrganizationVerificationStatus.UNDER_REVIEW,
                OrganizationVerificationStatus.NEEDS_INFORMATION,
            ])
            .order_by("submitted_at", "created_at", "id")
        )

        return Response(
            OrganizationVerificationCaseSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )


class OrganizationVerificationStartReviewView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        try:
            verification_case = start_verification_review(
                verification_case=verification_case,
                reviewer=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data
        )


class OrganizationVerificationNeedsInformationView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        serializer = OrganizationVerificationReviewNoteSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            verification_case = mark_verification_needs_information(
                verification_case=verification_case,
                reviewer=request.user,
                review_notes=serializer.validated_data["review_notes"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data
        )


class OrganizationVerificationApproveView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        serializer = OrganizationVerificationApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            grant = approve_verification_case(
                verification_case=verification_case,
                reviewer=request.user,
                expires_at=serializer.validated_data.get("expires_at"),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationGrantSerializer(
                grant,
                context={"request": request},
            ).data
        )


class OrganizationVerificationRejectView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        verification_case = _get_case(public_id)
        serializer = OrganizationVerificationReviewNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            verification_case = reject_verification_case(
                verification_case=verification_case,
                reviewer=request.user,
                review_notes=serializer.validated_data["review_notes"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationCaseSerializer(
                verification_case,
                context={"request": request},
            ).data
        )


class OrganizationVerificationDocumentReviewView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        document = OrganizationVerificationDocument.objects.filter(
            public_id=public_id
        ).first()
        if not document:
            raise NotFound("Verification document not found.")

        serializer = OrganizationVerificationDocumentReviewSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        document = review_verification_document(
            document=document,
            reviewer=request.user,
            **serializer.validated_data,
        )

        return Response(
            OrganizationVerificationDocumentSerializer(
                document,
                context={"request": request},
            ).data
        )


class OrganizationVerificationGrantRevokeView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        grant = OrganizationVerificationGrant.objects.filter(
            public_id=public_id
        ).first()
        if not grant:
            raise NotFound("Verification grant not found.")

        serializer = OrganizationVerificationRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            grant = revoke_verification_grant(
                grant=grant,
                reviewer=request.user,
                reason=serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationVerificationGrantSerializer(
                grant,
                context={"request": request},
            ).data
        )
