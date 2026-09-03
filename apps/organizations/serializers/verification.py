# apps/organizations/serializers/verification.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from rest_framework import serializers

from apps.organizations.constants import (
    OrganizationPermissionKey,
    OrganizationVerificationDocumentType,
    OrganizationVerificationPath,
)
from apps.organizations.models import (
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
    OrganizationVerificationGrant,
)


from apps.organizations.services.access import user_has_organization_permission


class OrganizationVerificationDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationVerificationDocument
        fields = [
            "public_id",
            "document_type",
            "title",
            "document_number",
            "issued_at",
            "expires_at",
            "file_url",
            "review_status",
            "review_note",
            "reviewed_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        if not obj.file:
            return None

        try:
            url = obj.file.url
        except Exception:
            return None

        request = self.context.get("request")
        if not request:
            return None

        user = getattr(request, "user", None)
        organization = obj.verification_case.organization
        can_view = bool(
            user
            and (
                getattr(user, "is_staff", False)
                or user_has_organization_permission(
                    user=user,
                    organization=organization,
                    permission_key=(
                        OrganizationPermissionKey.MANAGE_VERIFICATION
                    ),
                )
            )
        )

        if not can_view:
            return None

        return request.build_absolute_uri(url)


class OrganizationVerificationGrantSerializer(serializers.ModelSerializer):
    authority_organization = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationVerificationGrant
        fields = [
            "public_id",
            "grant_type",
            "status",
            "granted_at",
            "expires_at",
            "revoked_at",
            "revocation_reason",
            "authority_organization",
        ]
        read_only_fields = fields

    def get_authority_organization(self, obj):
        if not obj.relationship_id:
            return None

        organization = obj.relationship.source_organization
        return {
            "public_id": str(organization.public_id),
            "name": organization.name,
            "slug": organization.slug,
        }


class OrganizationVerificationCaseSerializer(serializers.ModelSerializer):
    documents = OrganizationVerificationDocumentSerializer(
        many=True,
        read_only=True,
    )
    grants = OrganizationVerificationGrantSerializer(
        many=True,
        read_only=True,
    )
    relationship_public_id = serializers.UUIDField(
        source="relationship.public_id",
        read_only=True,
        allow_null=True,
    )
    renewal_of_public_id = serializers.UUIDField(
        source="renewal_of.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = OrganizationVerificationCase
        fields = [
            "public_id",
            "path",
            "status",
            "renewal_of_public_id",
            "relationship_public_id",
            "legal_name",
            "registration_number",
            "jurisdiction_country",
            "jurisdiction_region",
            "registration_authority",
            "registered_address",
            "organization_notes",
            "review_notes",
            "submitted_at",
            "review_started_at",
            "decision_at",
            "documents",
            "grants",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrganizationVerificationCaseCreateSerializer(serializers.Serializer):
    path = serializers.ChoiceField(
        choices=OrganizationVerificationPath.choices,
        default=OrganizationVerificationPath.DIRECT,
    )
    relationship_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    legal_name = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=240,
    )
    registration_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=120,
    )
    jurisdiction_country = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=2,
    )
    jurisdiction_region = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=160,
    )
    registration_authority = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=240,
    )
    registered_address = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    organization_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class OrganizationVerificationDocumentCreateSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=OrganizationVerificationDocumentType.choices,
    )
    file = serializers.FileField()
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=240,
    )
    document_number = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=160,
    )
    issued_at = serializers.DateField(required=False, allow_null=True)
    expires_at = serializers.DateField(required=False, allow_null=True)


class OrganizationVerificationReviewNoteSerializer(serializers.Serializer):
    review_notes = serializers.CharField()


class OrganizationVerificationDocumentReviewSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )


class OrganizationVerificationApprovalSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )


class OrganizationVerificationRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)
