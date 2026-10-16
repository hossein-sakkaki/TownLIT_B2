# apps/organizations/serializers/people.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-30.
# Last Update by Hossein Sakkaki on 2026-09-30.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.constants import OrganizationRoleScope
from apps.organizations.models import OrganizationMembership, OrganizationRoleAssignment
from apps.organizations.serializers.membership import OrganizationMembershipSerializer
from apps.organizations.serializers.role import (
    OrganizationRoleAssignmentSerializer,
    OrganizationRoleSerializer,
)
from apps.profiles.models.member import Member


class OrganizationMemberCandidateSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = Member
        fields = [
            "user",
        ]
        read_only_fields = fields


class OrganizationMembershipInvitationCreateSerializer(serializers.Serializer):
    member_user_id = serializers.IntegerField(min_value=1)
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )

    def validate_message(self, value):
        if value is None:
            return None

        value = " ".join(str(value).split())
        return value or None


class OrganizationMembershipManagementSerializer(
    OrganizationMembershipSerializer
):
    role_assignments = serializers.SerializerMethodField()

    class Meta(OrganizationMembershipSerializer.Meta):
        fields = OrganizationMembershipSerializer.Meta.fields + [
            "role_assignments",
        ]
        read_only_fields = fields

    def get_role_assignments(self, obj: OrganizationMembership):
        assignments = getattr(
            obj,
            "active_role_assignments_cache",
            None,
        )

        if assignments is None:
            assignments = (
                obj.role_assignments
                .select_related("role")
                .prefetch_related("role__permissions")
                .filter(
                    is_active=True,
                    revoked_at__isnull=True,
                    role__is_active=True,
                )
                .order_by("-role__priority", "id")
            )

        return OrganizationRoleAssignmentSerializer(
            assignments,
            many=True,
            context=self.context,
        ).data


class OrganizationRoleAssignmentCreateSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    role_public_id = serializers.UUIDField()
    scope_type = serializers.ChoiceField(
        choices=OrganizationRoleScope.choices,
        default=OrganizationRoleScope.ORGANIZATION,
    )
    scope_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=120,
        default="",
    )

    def validate(self, attrs):
        scope_type = attrs.get(
            "scope_type",
            OrganizationRoleScope.ORGANIZATION,
        )
        scope_key = str(attrs.get("scope_key") or "").strip().lower()

        if scope_type == OrganizationRoleScope.ORGANIZATION:
            if scope_key:
                raise serializers.ValidationError({
                    "scope_key": (
                        "Organization-scoped roles cannot define a module scope key."
                    ),
                })
            scope_key = ""

        elif scope_type == OrganizationRoleScope.MODULE:
            if not scope_key:
                raise serializers.ValidationError({
                    "scope_key": (
                        "Module-scoped roles require a module scope key."
                    ),
                })

        attrs["scope_key"] = scope_key
        return attrs


class OrganizationRoleAssignmentManagementSerializer(serializers.ModelSerializer):
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
    )
    member_user = UserMiniSerializer(
        source="membership.member.user",
        read_only=True,
    )
    role = OrganizationRoleSerializer(read_only=True)

    class Meta:
        model = OrganizationRoleAssignment
        fields = [
            "public_id",
            "membership_public_id",
            "member_user",
            "role",
            "scope_type",
            "scope_key",
            "starts_at",
            "ends_at",
            "revoked_at",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields
