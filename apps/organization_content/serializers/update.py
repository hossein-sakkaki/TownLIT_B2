# apps/organization_content/serializers/update.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-09-28.

from rest_framework import serializers

from apps.organization_content.models import OrganizationUpdate
from apps.organization_content.services.feed import feed_entry_for_target
from apps.organization_media.serializers import OrganizationMediaAssetSerializer


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    organization_public_id = serializers.UUIDField(
        source="organization.public_id",
        read_only=True,
    )
    media = serializers.SerializerMethodField()
    home_visibility = serializers.SerializerMethodField()
    is_publicly_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationUpdate
        fields = [
            "public_id",
            "organization_public_id",
            "caption",
            "status",
            "media",
            "home_visibility",
            "is_publicly_available",
            "published_at",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_media(self, obj):
        assets = [
            usage.asset
            for usage in obj.media_items.all()
        ]

        return OrganizationMediaAssetSerializer(
            assets,
            many=True,
            context=self.context,
        ).data

    def get_home_visibility(self, obj):
        entry = feed_entry_for_target(
            organization=obj.organization,
            target=obj,
        )

        if not entry:
            return None

        return {
            "is_active": entry.is_active,
            "is_pinned": entry.is_pinned,
            "starts_at": entry.starts_at,
            "expires_at": entry.expires_at,
        }


class PublicOrganizationUpdateSerializer(serializers.ModelSerializer):
    organization_public_id = serializers.UUIDField(
        source="organization.public_id",
        read_only=True,
    )
    media = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUpdate
        fields = [
            "public_id",
            "organization_public_id",
            "caption",
            "status",
            "media",
            "published_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_media(self, obj):
        assets = [
            usage.asset
            for usage in obj.media_items.all()
        ]

        return OrganizationMediaAssetSerializer(
            assets,
            many=True,
            context=self.context,
        ).data


class OrganizationUpdateCreateSerializer(serializers.Serializer):
    caption = serializers.CharField()
    media_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )


class OrganizationUpdatePatchSerializer(serializers.Serializer):
    caption = serializers.CharField(required=False)
    media_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
    )


class OrganizationUpdatePublishSerializer(serializers.Serializer):
    publish_at = serializers.DateTimeField(required=False, allow_null=True)
    show_on_home = serializers.BooleanField(required=False, default=True)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    is_pinned = serializers.BooleanField(required=False, default=False)


class OrganizationUpdateHomeVisibilitySerializer(serializers.Serializer):
    show = serializers.BooleanField()
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    is_pinned = serializers.BooleanField(required=False, default=False)