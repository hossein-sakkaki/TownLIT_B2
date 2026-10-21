# apps/organization_content/serializers/update.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-10-20.

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
    is_under_review = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUpdate
        fields = [
            "id",
            "public_id",
            "organization_public_id",
            "caption",
            "status",
            "media",
            "home_visibility",
            "is_publicly_available",
            "is_under_review",
            "published_at",
            "archived_at",
            "publish_requested_at",
            "publish_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_under_review(self, obj):
        from apps.sanctuary.services.held_content_access import is_under_active_safety_hold
        return is_under_active_safety_hold(obj)

    def to_representation(self, instance):
        from apps.sanctuary.services.held_content_access import can_inspect_held_content
        data = super().to_representation(instance)
        viewer = getattr(self.context.get("request"), "user", None)
        if not can_inspect_held_content(viewer=viewer, target=instance):
            data["caption"] = "This content is temporarily unavailable during review."
            data["media"] = []
        return data

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
            "id",
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
    public_id = serializers.UUIDField(required=False)
    caption = serializers.CharField()
    media_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )


class OrganizationUpdatePatchSerializer(serializers.Serializer):
    expected_updated_at = serializers.DateTimeField(required=False)
    caption = serializers.CharField(required=False)
    media_public_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
    )


class OrganizationUpdatePublishSerializer(serializers.Serializer):
    expected_updated_at = serializers.DateTimeField(required=False)
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

