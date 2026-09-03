# apps/organizations/serializers/modules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from rest_framework import serializers

from apps.organizations.constants import OrganizationModuleVisibility
from apps.organizations.models import (
    OrganizationModuleActivation,
    OrganizationModuleDefinition,
)


class OrganizationModuleDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationModuleDefinition
        fields = [
            "key",
            "name",
            "description",
            "requires_verification",
            "requires_entitlement",
            "fallback_access_mode",
            "schema_version",
            "sort_order",
            "is_public_catalog",
            "is_active",
        ]
        read_only_fields = fields


class OrganizationModuleActivationSerializer(serializers.ModelSerializer):
    module = OrganizationModuleDefinitionSerializer(read_only=True)
    effective_name = serializers.CharField(read_only=True)

    class Meta:
        model = OrganizationModuleActivation
        fields = [
            "public_id",
            "module",
            "display_name",
            "effective_name",
            "summary",
            "visibility",
            "status",
            "activated_at",
            "disabled_at",
            "suspended_at",
            "configuration",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrganizationModuleAccessSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    visibility = serializers.CharField(allow_null=True)
    access_mode = serializers.CharField()
    reason = serializers.CharField()
    is_verified = serializers.BooleanField()
    has_entitlement = serializers.BooleanField(allow_null=True)
    can_manage = serializers.BooleanField()
    can_write = serializers.BooleanField()
    activated = serializers.BooleanField()
    activation_public_id = serializers.UUIDField(allow_null=True)
    display_name = serializers.CharField(allow_null=True)
    summary = serializers.CharField(allow_null=True)
    schema_version = serializers.IntegerField()


class OrganizationModuleActivationWriteSerializer(serializers.Serializer):
    display_name = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=160,
    )
    summary = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationModuleVisibility.choices,
        required=False,
    )


class OrganizationModuleSuspensionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)
