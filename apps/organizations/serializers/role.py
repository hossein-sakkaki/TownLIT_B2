# apps/organizations/serializers/role.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from rest_framework import serializers

from apps.organizations.models import (
    OrganizationRole,
    OrganizationRoleAssignment,
)


class OrganizationRoleSerializer(serializers.ModelSerializer):
    permission_keys = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationRole
        fields = [
            "public_id",
            "key",
            "name",
            "description",
            "priority",
            "is_system",
            "is_protected",
            "is_active",
            "permission_keys",
        ]
        read_only_fields = fields

    def get_permission_keys(self, obj):
        return list(
            obj.permissions
            .filter(is_active=True)
            .order_by("key")
            .values_list("key", flat=True)
        )


class OrganizationRoleAssignmentSerializer(serializers.ModelSerializer):
    role = OrganizationRoleSerializer(read_only=True)

    class Meta:
        model = OrganizationRoleAssignment
        fields = [
            "public_id",
            "membership_id",
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
