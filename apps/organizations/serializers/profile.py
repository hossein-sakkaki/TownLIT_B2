# apps/organizations/serializers/profile.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.
#

from rest_framework import serializers

from apps.accounts.models.social import (
    SocialMediaLink,
    SocialMediaType,
)
from apps.accounts.serializers.user_serializers import (
    LimitedCustomUserSerializer,
)
from apps.organizations.constants import (
    OrganizationRepresentativeStatus,
)
from apps.organizations.models import (
    OrganizationBusinessHour,
    OrganizationContactPoint,
    OrganizationMembership,
    OrganizationRepresentative,
)


class OrganizationContactPointSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = OrganizationContactPoint

        fields = [
            "public_id",
            "channel",
            "label",
            "value",
            "is_primary",
            "is_public",
            "sort_order",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "public_id",
            "created_at",
            "updated_at",
        ]


class OrganizationBusinessHourSerializer(
    serializers.ModelSerializer
):
    weekday_display = serializers.CharField(
        source="get_weekday_display",
        read_only=True,
    )

    class Meta:
        model = OrganizationBusinessHour

        fields = [
            "public_id",
            "weekday",
            "weekday_display",
            "opens_at",
            "closes_at",
            "is_closed",
            "is_24_hours",
            "label",
            "sort_order",
        ]

        read_only_fields = [
            "public_id",
            "weekday_display",
        ]


class OrganizationRepresentativeSerializer(
    serializers.ModelSerializer
):
    membership_public_id = serializers.UUIDField(
        source="membership.public_id",
        read_only=True,
    )

    user = LimitedCustomUserSerializer(
        source="membership.member.user",
        read_only=True,
    )

    class Meta:
        model = OrganizationRepresentative

        fields = [
            "public_id",
            "membership_public_id",
            "user",
            "role_title",
            "status",
            "is_primary",
            "sort_order",
            "responded_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class OrganizationRepresentativeCreateSerializer(
    serializers.Serializer
):
    membership_public_id = serializers.UUIDField()

    role_title = serializers.CharField(
        max_length=160,
    )

    is_primary = serializers.BooleanField(
        required=False,
        default=False,
    )

    sort_order = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        max_value=32767,
    )


class OrganizationRepresentativeResponseSerializer(
    serializers.Serializer
):
    decision = serializers.ChoiceField(
        choices=[
            OrganizationRepresentativeStatus.ACCEPTED,
            OrganizationRepresentativeStatus.DECLINED,
        ]
    )


class OrganizationRepresentativeCandidateSerializer(
    serializers.ModelSerializer
):
    membership_public_id = serializers.UUIDField(
        source="public_id",
        read_only=True,
    )

    user = LimitedCustomUserSerializer(
        source="member.user",
        read_only=True,
    )

    class Meta:
        model = OrganizationMembership

        fields = [
            "membership_public_id",
            "user",
            "joined_at",
        ]

        read_only_fields = fields


class OrganizationSocialMediaTypeSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = SocialMediaType

        fields = [
            "id",
            "name",
            "icon_class",
            "icon_svg",
        ]

        read_only_fields = fields


class OrganizationSocialLinkSerializer(
    serializers.ModelSerializer
):
    social_media_type = (
        OrganizationSocialMediaTypeSerializer(
            read_only=True
        )
    )

    class Meta:
        model = SocialMediaLink

        fields = [
            "id",
            "social_media_type",
            "link",
            "is_active",
        ]

        read_only_fields = fields


class OrganizationSocialLinkWriteSerializer(
    serializers.Serializer
):
    social_media_type = serializers.PrimaryKeyRelatedField(
        queryset=SocialMediaType.objects.filter(
            is_active=True
        )
    )

    link = serializers.URLField(
        max_length=500,
    )

    is_active = serializers.BooleanField(
        required=False,
        default=True,
    )