# apps/organizations/modules/church/serializers/operations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.modules.church.constants import (
    ChurchServicePlanItemType,
    ChurchServingTeamStatus,
)
from apps.organizations.modules.church.models import (
    ChurchServicePlan,
    ChurchServicePlanItem,
    ChurchServingAssignment,
    ChurchServingTeam,
    ChurchServingTeamMembership,
)


class ChurchServingTeamSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = ChurchServingTeam
        fields = [
            "public_id",
            "campus_public_id",
            "ministry_public_id",
            "name",
            "slug",
            "description",
            "status",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchServingTeamCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    sort_order = serializers.IntegerField(
        required=False,
        default=100,
        min_value=0,
        max_value=65535,
    )


class ChurchServingTeamUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=160)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    status = serializers.ChoiceField(
        choices=ChurchServingTeamStatus.choices,
        required=False,
    )
    sort_order = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=65535,
    )


class ChurchServingTeamMembershipSerializer(serializers.ModelSerializer):
    team_public_id = serializers.UUIDField(
        source="team.public_id",
        read_only=True,
    )
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
    )
    member_user = UserMiniSerializer(
        source="membership.member.user",
        read_only=True,
    )

    class Meta:
        model = ChurchServingTeamMembership
        fields = [
            "public_id",
            "team_public_id",
            "membership_public_id",
            "member_user",
            "role_title",
            "is_team_lead",
            "is_publicly_listed",
            "status",
            "joined_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchServingTeamMemberAddSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    role_title = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=120,
    )
    is_team_lead = serializers.BooleanField(required=False, default=False)
    publicly_listed = serializers.BooleanField(required=False, default=False)


class ChurchServicePlanItemSerializer(serializers.ModelSerializer):
    serving_team_public_id = serializers.UUIDField(
        source="serving_team.public_id",
        read_only=True,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        source="ministry.public_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchServicePlanItem
        fields = [
            "public_id",
            "serving_team_public_id",
            "ministry_public_id",
            "item_type",
            "title",
            "notes",
            "planned_duration_seconds",
            "sort_order",
            "is_optional",
            "is_internal_only",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchServicePlanReferenceSerializer(serializers.ModelSerializer):
    occurrence_public_id = serializers.UUIDField(
        source="occurrence.public_id",
        read_only=True,
    )
    occurrence_title = serializers.CharField(
        source="occurrence.title",
        read_only=True,
    )
    occurrence_starts_at = serializers.DateTimeField(
        source="occurrence.starts_at",
        read_only=True,
    )

    class Meta:
        model = ChurchServicePlan
        fields = [
            "public_id",
            "occurrence_public_id",
            "occurrence_title",
            "occurrence_starts_at",
            "theme",
            "status",
        ]
        read_only_fields = fields


class ChurchServicePlanSerializer(serializers.ModelSerializer):
    occurrence_public_id = serializers.UUIDField(
        source="occurrence.public_id",
        read_only=True,
    )
    occurrence_title = serializers.CharField(
        source="occurrence.title",
        read_only=True,
    )
    occurrence_starts_at = serializers.DateTimeField(
        source="occurrence.starts_at",
        read_only=True,
    )
    items = ChurchServicePlanItemSerializer(many=True, read_only=True)

    class Meta:
        model = ChurchServicePlan
        fields = [
            "public_id",
            "occurrence_public_id",
            "occurrence_title",
            "occurrence_starts_at",
            "theme",
            "internal_notes",
            "status",
            "published_at",
            "completed_at",
            "canceled_at",
            "metadata",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchServicePlanCreateSerializer(serializers.Serializer):
    occurrence_public_id = serializers.UUIDField()
    theme = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=180,
    )
    internal_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class ChurchServicePlanUpdateSerializer(serializers.Serializer):
    theme = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=180,
    )
    internal_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class ChurchServicePlanItemCreateSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=ChurchServicePlanItemType.choices)
    title = serializers.CharField(max_length=180)
    serving_team_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    planned_duration_seconds = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        max_value=14400,
    )
    sort_order = serializers.IntegerField(required=False, default=100, min_value=0)
    is_optional = serializers.BooleanField(required=False, default=False)
    is_internal_only = serializers.BooleanField(required=False, default=False)


class ChurchServicePlanItemUpdateSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(
        choices=ChurchServicePlanItemType.choices,
        required=False,
    )
    title = serializers.CharField(required=False, max_length=180)
    serving_team_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    planned_duration_seconds = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=14400,
    )
    sort_order = serializers.IntegerField(required=False, min_value=0)
    is_optional = serializers.BooleanField(required=False)
    is_internal_only = serializers.BooleanField(required=False)


class ChurchServingAssignmentSerializer(serializers.ModelSerializer):
    service_plan_public_id = serializers.UUIDField(
        source="service_plan.public_id",
        read_only=True,
    )
    occurrence_public_id = serializers.UUIDField(
        source="service_plan.occurrence.public_id",
        read_only=True,
    )
    occurrence_title = serializers.CharField(
        source="service_plan.occurrence.title",
        read_only=True,
    )
    occurrence_starts_at = serializers.DateTimeField(
        source="service_plan.occurrence.starts_at",
        read_only=True,
    )
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
    )
    member_user = UserMiniSerializer(
        source="membership.member.user",
        read_only=True,
    )
    team_public_id = serializers.UUIDField(
        source="team.public_id",
        read_only=True,
        allow_null=True,
    )
    team_name = serializers.CharField(
        source="team.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchServingAssignment
        fields = [
            "public_id",
            "service_plan_public_id",
            "occurrence_public_id",
            "occurrence_title",
            "occurrence_starts_at",
            "membership_public_id",
            "member_user",
            "team_public_id",
            "team_name",
            "role_label",
            "status",
            "invited_at",
            "responded_at",
            "canceled_at",
            "checked_in_at",
            "checked_out_at",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchServingAssignmentCreateSerializer(serializers.Serializer):
    service_plan_public_id = serializers.UUIDField()
    membership_public_id = serializers.UUIDField()
    team_public_id = serializers.UUIDField(required=False, allow_null=True)
    role_label = serializers.CharField(max_length=120)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )


class ChurchServingAssignmentRespondSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
