# apps/organizations/modules/church/serializers/congregation.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-08.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.modules.church.constants import (
    ChurchCongregantStatus,
    ChurchDirectoryVisibility,
    ChurchHouseholdRelationship,
    ChurchHouseholdStatus,
)
from apps.organizations.modules.church.models import (
    ChurchCongregant,
    ChurchHousehold,
    ChurchHouseholdMembership,
)
from apps.organizations.modules.church.selectors.congregation import (
    get_church_congregant_display_name,
)


class ChurchCongregantSerializer(serializers.ModelSerializer):
    identity_kind = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    official_membership_public_id = serializers.UUIDField(
        source="official_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    campus_name = serializers.CharField(
        source="campus.name",
        read_only=True,
        allow_null=True,
    )
    is_current_official_member = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChurchCongregant
        fields = [
            "public_id",
            "identity_kind",
            "display_name",
            "user",
            "official_membership_public_id",
            "preferred_name",
            "status",
            "source",
            "campus_public_id",
            "campus_name",
            "directory_visibility",
            "directory_consent_at",
            "first_seen_at",
            "last_seen_at",
            "is_active",
            "is_current_official_member",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_identity_kind(self, obj):
        if obj.member_id:
            return "member"
        if obj.guest_profile_id:
            return "guest"
        return "external"

    def get_display_name(self, obj):
        return get_church_congregant_display_name(obj)

    def get_user(self, obj):
        user = None
        if obj.member_id:
            user = obj.member.user
        elif obj.guest_profile_id:
            user = obj.guest_profile.user

        if user is None:
            return None

        return UserMiniSerializer(
            user,
            context=self.context,
        ).data


class ChurchMemberDirectoryEntrySerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    campus_name = serializers.CharField(
        source="campus.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ChurchCongregant
        fields = [
            "public_id",
            "display_name",
            "user",
            "campus_public_id",
            "campus_name",
        ]
        read_only_fields = fields

    def get_display_name(self, obj):
        return get_church_congregant_display_name(obj)

    def get_user(self, obj):
        if not obj.member_id:
            return None
        return UserMiniSerializer(
            obj.member.user,
            context=self.context,
        ).data


class ChurchMemberCongregantCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=ChurchCongregantStatus.choices,
        default=ChurchCongregantStatus.REGULAR,
    )


class ChurchGuestCongregantCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=ChurchCongregantStatus.choices,
        default=ChurchCongregantStatus.NEWCOMER,
    )


class ChurchExternalCongregantCreateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=160)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=ChurchCongregantStatus.choices,
        default=ChurchCongregantStatus.NEWCOMER,
    )


class ChurchCongregantUpdateSerializer(serializers.Serializer):
    campus_public_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(
        choices=ChurchCongregantStatus.choices,
        required=False,
    )
    preferred_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=80,
    )
    is_active = serializers.BooleanField(required=False)
    last_seen_at = serializers.DateTimeField(required=False)


class ChurchDirectoryVisibilityUpdateSerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(
        choices=ChurchDirectoryVisibility.choices,
    )


class ChurchHouseholdMembershipSerializer(serializers.ModelSerializer):
    congregant = ChurchMemberDirectoryEntrySerializer(read_only=True)

    class Meta:
        model = ChurchHouseholdMembership
        fields = [
            "public_id",
            "congregant",
            "relationship_type",
            "status",
            "is_primary",
            "joined_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChurchHouseholdSerializer(serializers.ModelSerializer):
    campus_public_id = serializers.UUIDField(
        source="campus.public_id",
        read_only=True,
        allow_null=True,
    )
    campus_name = serializers.CharField(
        source="campus.name",
        read_only=True,
        allow_null=True,
    )
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = ChurchHousehold
        fields = [
            "public_id",
            "name",
            "campus_public_id",
            "campus_name",
            "status",
            "memberships",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_memberships(self, obj):
        memberships = obj.memberships.all()
        return ChurchHouseholdMembershipSerializer(
            memberships,
            many=True,
            context=self.context,
        ).data


class ChurchHouseholdCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    campus_public_id = serializers.UUIDField(required=False, allow_null=True)


class ChurchHouseholdUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=160)
    campus_public_id = serializers.UUIDField(required=False)


class ChurchHouseholdMemberAddSerializer(serializers.Serializer):
    congregant_public_id = serializers.UUIDField()
    relationship_type = serializers.ChoiceField(
        choices=ChurchHouseholdRelationship.choices,
        default=ChurchHouseholdRelationship.OTHER,
    )
    is_primary = serializers.BooleanField(default=False)
