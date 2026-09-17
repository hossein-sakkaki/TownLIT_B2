# apps/organizations/modules/church/serializers/resources.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.organizations.modules.church.constants import (
    ChurchResourceStatus,
    ChurchResourceType,
)
from apps.organizations.modules.church.models import (
    ChurchResource,
    ChurchResourceReservation,
)


class ChurchResourceSerializer(serializers.ModelSerializer):
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
        model = ChurchResource
        fields = [
            "public_id",
            "campus_public_id",
            "ministry_public_id",
            "resource_type",
            "name",
            "slug",
            "description",
            "status",
            "is_reservable",
            "quantity_available",
            "capacity",
            "sort_order",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchResourceCreateSerializer(serializers.Serializer):
    resource_type = serializers.ChoiceField(choices=ChurchResourceType.choices)
    name = serializers.CharField(max_length=160)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    ministry_public_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1500,
    )
    is_reservable = serializers.BooleanField(required=False, default=True)
    quantity_available = serializers.IntegerField(required=False, default=1, min_value=1)
    capacity = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    sort_order = serializers.IntegerField(
        required=False,
        default=100,
        min_value=0,
        max_value=65535,
    )


class ChurchResourceUpdateSerializer(serializers.Serializer):
    resource_type = serializers.ChoiceField(
        choices=ChurchResourceType.choices,
        required=False,
    )
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
        choices=ChurchResourceStatus.choices,
        required=False,
    )
    is_reservable = serializers.BooleanField(required=False)
    quantity_available = serializers.IntegerField(required=False, min_value=1)
    capacity = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    sort_order = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=65535,
    )


class ChurchResourceReservationSerializer(serializers.ModelSerializer):
    resource_public_id = serializers.UUIDField(
        source="resource.public_id",
        read_only=True,
    )
    occurrence_public_id = serializers.UUIDField(
        source="occurrence.public_id",
        read_only=True,
    )
    occurrence_title = serializers.CharField(
        source="occurrence.title",
        read_only=True,
    )

    class Meta:
        model = ChurchResourceReservation
        fields = [
            "public_id",
            "resource_public_id",
            "occurrence_public_id",
            "occurrence_title",
            "quantity",
            "starts_at",
            "ends_at",
            "status",
            "canceled_at",
            "completed_at",
            "notes",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchResourceReservationCreateSerializer(serializers.Serializer):
    occurrence_public_id = serializers.UUIDField()
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )
