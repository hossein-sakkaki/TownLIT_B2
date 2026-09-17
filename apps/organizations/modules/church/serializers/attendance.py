# apps/organizations/modules/church/serializers/attendance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.modules.church.constants import (
    ChurchAttendancePresence,
    ChurchAttendanceSource,
)
from apps.organizations.modules.church.models import (
    ChurchAttendanceRecord,
    ChurchAttendanceSession,
)


class ChurchAttendanceRecordSerializer(serializers.ModelSerializer):
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
    )
    member_user = UserMiniSerializer(
        source="membership.member.user",
        read_only=True,
    )

    class Meta:
        model = ChurchAttendanceRecord
        fields = [
            "public_id",
            "membership_public_id",
            "member_user",
            "presence",
            "source",
            "checked_in_at",
            "checked_out_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchAttendanceSessionSerializer(serializers.ModelSerializer):
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
    registered_attendee_count = serializers.IntegerField(read_only=True)
    aggregate_guest_count = serializers.IntegerField(read_only=True)
    total_attendance_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChurchAttendanceSession
        fields = [
            "public_id",
            "occurrence_public_id",
            "occurrence_title",
            "occurrence_starts_at",
            "status",
            "opened_at",
            "closed_at",
            "unregistered_adult_count",
            "unregistered_child_count",
            "anonymous_online_count",
            "registered_attendee_count",
            "aggregate_guest_count",
            "total_attendance_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchAttendanceSessionDetailSerializer(ChurchAttendanceSessionSerializer):
    records = ChurchAttendanceRecordSerializer(many=True, read_only=True)

    class Meta(ChurchAttendanceSessionSerializer.Meta):
        fields = ChurchAttendanceSessionSerializer.Meta.fields + ["records"]
        read_only_fields = fields


class ChurchAttendanceOpenSerializer(serializers.Serializer):
    occurrence_public_id = serializers.UUIDField()


class ChurchAttendanceCheckInSerializer(serializers.Serializer):
    membership_public_id = serializers.UUIDField()
    presence = serializers.ChoiceField(
        choices=ChurchAttendancePresence.choices,
        required=False,
        default=ChurchAttendancePresence.PRESENT,
    )
    source = serializers.ChoiceField(
        choices=ChurchAttendanceSource.choices,
        required=False,
        default=ChurchAttendanceSource.MANUAL,
    )


class ChurchAttendanceGuestCountsSerializer(serializers.Serializer):
    unregistered_adult_count = serializers.IntegerField(min_value=0)
    unregistered_child_count = serializers.IntegerField(min_value=0)
    anonymous_online_count = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
    )
