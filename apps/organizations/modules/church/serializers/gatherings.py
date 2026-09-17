# apps/organizations/modules/church/serializers/gatherings.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.organizations.constants import OrganizationModuleVisibility
from apps.organizations.modules.church.constants import (
    ChurchGatheringSeriesStatus,
    ChurchGatheringType,
    ChurchMonthlyWeek,
    ChurchRecurrenceFrequency,
)
from apps.organizations.modules.church.models import (
    ChurchGatheringOccurrence,
    ChurchGatheringSeries,
)


class ChurchGatheringSeriesSerializer(serializers.ModelSerializer):
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
        model = ChurchGatheringSeries
        fields = [
            "public_id",
            "campus_public_id",
            "ministry_public_id",
            "name",
            "gathering_type",
            "description",
            "location_label",
            "visibility",
            "status",
            "recurrence_frequency",
            "weekday",
            "monthly_week",
            "local_start_time",
            "duration_minutes",
            "effective_start_date",
            "effective_end_date",
            "auto_create_attendance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchGatheringSeriesCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    gathering_type = serializers.ChoiceField(
        choices=ChurchGatheringType.choices,
    )
    recurrence_frequency = serializers.ChoiceField(
        choices=ChurchRecurrenceFrequency.choices,
    )
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    local_start_time = serializers.TimeField()
    effective_start_date = serializers.DateField()
    campus_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    monthly_week = serializers.ChoiceField(
        choices=ChurchMonthlyWeek.choices,
        required=False,
        allow_null=True,
    )
    duration_minutes = serializers.IntegerField(
        required=False,
        min_value=15,
        max_value=720,
    )
    effective_end_date = serializers.DateField(
        required=False,
        allow_null=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    location_label = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=250,
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationModuleVisibility.choices,
        required=False,
        default=OrganizationModuleVisibility.PUBLIC,
    )
    auto_create_attendance = serializers.BooleanField(
        required=False,
        default=False,
    )


class ChurchGatheringSeriesUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=180)
    gathering_type = serializers.ChoiceField(
        choices=ChurchGatheringType.choices,
        required=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    location_label = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=250,
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationModuleVisibility.choices,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=ChurchGatheringSeriesStatus.choices,
        required=False,
    )
    recurrence_frequency = serializers.ChoiceField(
        choices=ChurchRecurrenceFrequency.choices,
        required=False,
    )
    weekday = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=6,
    )
    monthly_week = serializers.ChoiceField(
        choices=ChurchMonthlyWeek.choices,
        required=False,
        allow_null=True,
    )
    local_start_time = serializers.TimeField(required=False)
    duration_minutes = serializers.IntegerField(
        required=False,
        min_value=15,
        max_value=720,
    )
    effective_start_date = serializers.DateField(required=False)
    effective_end_date = serializers.DateField(
        required=False,
        allow_null=True,
    )
    auto_create_attendance = serializers.BooleanField(required=False)
    campus_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )


class ChurchGatheringMaterializeSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    through_date = serializers.DateField()


class ChurchGatheringOccurrenceSerializer(serializers.ModelSerializer):
    series_public_id = serializers.UUIDField(
        source="series.public_id",
        read_only=True,
        allow_null=True,
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

    class Meta:
        model = ChurchGatheringOccurrence
        fields = [
            "public_id",
            "series_public_id",
            "campus_public_id",
            "ministry_public_id",
            "title",
            "gathering_type",
            "location_label",
            "visibility",
            "starts_at",
            "ends_at",
            "status",
            "source",
            "canceled_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchGatheringOccurrenceCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180)
    gathering_type = serializers.ChoiceField(
        choices=ChurchGatheringType.choices,
    )
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    campus_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    ministry_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    location_label = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=250,
    )
    visibility = serializers.ChoiceField(
        choices=OrganizationModuleVisibility.choices,
        required=False,
        default=OrganizationModuleVisibility.PUBLIC,
    )
