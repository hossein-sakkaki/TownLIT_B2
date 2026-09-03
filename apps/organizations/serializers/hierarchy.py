# apps/organizations/serializers/hierarchy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from rest_framework import serializers

from apps.organizations.constants import (
    OrganizationPermissionKey,
    OrganizationRelationshipType,
)
from apps.organizations.models import (
    OrganizationRelationship,
    OrganizationRelationshipConsent,
)


from apps.organizations.services.access import user_has_organization_permission


class OrganizationRelationshipConsentSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    governance_proposal_public_id = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationRelationshipConsent
        fields = [
            "organization",
            "status",
            "governance_proposal_public_id",
            "decided_at",
            "note",
        ]
        read_only_fields = fields


    def get_governance_proposal_public_id(self, obj):
        if not obj.governance_proposal_id:
            return None

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        if not user:
            return None

        if getattr(user, "is_staff", False) or user_has_organization_permission(
            user=user,
            organization=obj.organization,
            permission_key=OrganizationPermissionKey.MANAGE_GOVERNANCE,
        ):
            return str(obj.governance_proposal.public_id)

        return None

    def get_organization(self, obj):
        organization = obj.organization
        return {
            "public_id": str(organization.public_id),
            "name": organization.name,
            "slug": organization.slug,
        }


class OrganizationRelationshipSerializer(serializers.ModelSerializer):
    source_organization = serializers.SerializerMethodField()
    target_organization = serializers.SerializerMethodField()
    requested_by_organization = serializers.SerializerMethodField()
    consents = OrganizationRelationshipConsentSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = OrganizationRelationship
        fields = [
            "public_id",
            "source_organization",
            "target_organization",
            "relationship_type",
            "status",
            "requested_by_organization",
            "activated_at",
            "suspended_at",
            "ended_at",
            "end_reason",
            "consents",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @staticmethod
    def _organization_payload(organization):
        if not organization:
            return None

        return {
            "public_id": str(organization.public_id),
            "name": organization.name,
            "slug": organization.slug,
        }

    def get_source_organization(self, obj):
        return self._organization_payload(obj.source_organization)

    def get_target_organization(self, obj):
        return self._organization_payload(obj.target_organization)

    def get_requested_by_organization(self, obj):
        return self._organization_payload(obj.requested_by_organization)


class OrganizationRelationshipCreateSerializer(serializers.Serializer):
    source_organization_slug = serializers.SlugField()
    target_organization_slug = serializers.SlugField()
    relationship_type = serializers.ChoiceField(
        choices=OrganizationRelationshipType.choices,
    )
    requested_by_organization_slug = serializers.SlugField()
    metadata = serializers.JSONField(required=False)


class OrganizationRelationshipConsentProposalSerializer(serializers.Serializer):
    organization_slug = serializers.SlugField()
