# apps/organizations/modules/church/serializers/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.constants import OrganizationModuleVisibility
from apps.organizations.modules.church.constants import (
    ChurchCampusStatus,
    ChurchLeadershipPositionType,
    ChurchMinistryStatus,
)
from apps.organizations.modules.church.models import (
    ChurchCampus,
    ChurchLeadershipAssignment,
    ChurchMinistry,
    ChurchWorkspace,
)


class ChurchWorkspaceSerializer(serializers.ModelSerializer):
    organization_public_id = serializers.UUIDField(
        source="activation.organization.public_id",
        read_only=True,
    )
    organization_slug = serializers.CharField(
        source="activation.organization.slug",
        read_only=True,
    )
    effective_timezone = serializers.CharField(read_only=True)

    class Meta:
        model = ChurchWorkspace
        fields = [
            "public_id",
            "organization_public_id",
            "organization_slug",
            "timezone_override",
            "effective_timezone",
            "membership_directory_enabled",
            "attendance_tracking_enabled",
            "default_gathering_duration_minutes",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchWorkspaceUpdateSerializer(serializers.Serializer):
    timezone_override = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )
    membership_directory_enabled = serializers.BooleanField(required=False)
    attendance_tracking_enabled = serializers.BooleanField(required=False)
    default_gathering_duration_minutes = serializers.IntegerField(
        required=False,
        min_value=15,
        max_value=720,
    )
    settings = serializers.JSONField(required=False)


class ChurchCampusSerializer(serializers.ModelSerializer):
    address_id = serializers.IntegerField(read_only=True)
    effective_timezone = serializers.CharField(read_only=True)

    class Meta:
        model = ChurchCampus
        fields = [
            "public_id",
            "name",
            "slug",
            "description",
            "address_id",
            "public_email",
            "public_phone",
            "website_url",
            "timezone_override",
            "effective_timezone",
            "status",
            "is_primary",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchCampusCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )
    address_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    public_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    public_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=30,
    )
    website_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=500,
    )
    timezone_override = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=64,
    )
    is_primary = serializers.BooleanField(required=False, default=False)
    sort_order = serializers.IntegerField(
        required=False,
        default=100,
        min_value=0,
        max_value=65535,
    )


class ChurchCampusUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=160)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )
    address_id = serializers.IntegerField(
        required=False,
        min_value=1,
    )
    public_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    public_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=30,
    )
    website_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=500,
    )
    timezone_override = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=64,
    )
    sort_order = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=65535,
    )


class ChurchMinistrySerializer(serializers.ModelSerializer):
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchMinistry
        fields = [
            "public_id",
            "campus_public_id",
            "name",
            "slug",
            "description",
            "visibility",
            "status",
            "is_accepting_participants",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchMinistryCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    campus_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationModuleVisibility.choices,
        required=False,
        default=OrganizationModuleVisibility.PUBLIC,
    )
    is_accepting_participants = serializers.BooleanField(
        required=False,
        default=True,
    )
    sort_order = serializers.IntegerField(
        required=False,
        default=100,
        min_value=0,
        max_value=65535,
    )


class ChurchMinistryUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=160)
    campus_public_id = serializers.UUIDField(required=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationModuleVisibility.choices,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=ChurchMinistryStatus.choices,
        required=False,
    )
    is_accepting_participants = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=65535,
    )


class ChurchLeadershipAssignmentSerializer(serializers.ModelSerializer):
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
    )
    member_user = UserMiniSerializer(
        source="membership.member.user",
        read_only=True,
    )
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        source="ministry.public_id",
        read_only=True,
        allow_null=True,
    )
    effective_title = serializers.CharField(read_only=True)

    class Meta:
        model = ChurchLeadershipAssignment
        fields = [
            "public_id",
            "membership_public_id",
            "member_user",
            "campus_public_id",
            "ministry_public_id",
            "position_type",
            "custom_title",
            "effective_title",
            "status",
            "publicly_listed",
            "sort_order",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchLeadershipAssignSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    position_type = serializers.ChoiceField(
        choices=ChurchLeadershipPositionType.choices,
    )
    custom_title = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=160,
    )
    campus_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    publicly_listed = serializers.BooleanField(required=False, default=False)
    sort_order = serializers.IntegerField(
        required=False,
        default=100,
        min_value=0,
        max_value=65535,
    )
    started_at = serializers.DateTimeField(required=False)
