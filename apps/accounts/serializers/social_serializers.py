# apps/accounts/serializers/social_serializers.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from rest_framework import serializers

from apps.accounts.models.social import (
    SocialMediaLink,
    SocialMediaType,
)
from apps.accounts.services.social_links import (
    resolve_social_owner_for_management,
    social_content_type_for_key,
)
from apps.organizations.models import Organization


class SocialMediaTypeSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = SocialMediaType
        fields = [
            "id",
            "name",
            "icon_class",
            "icon_svg",
            "is_active",
        ]


class SocialMediaLinkSerializer(
    serializers.ModelSerializer
):
    social_media_type = (
        serializers.PrimaryKeyRelatedField(
            queryset=(
                SocialMediaType.objects
                .filter(is_active=True)
            )
        )
    )
    content_type = serializers.CharField(
        write_only=True
    )
    object_id = serializers.IntegerField(
        write_only=True
    )
    content_object = (
        serializers.SerializerMethodField(
            read_only=True
        )
    )

    class Meta:
        model = SocialMediaLink
        fields = [
            "id",
            "social_media_type",
            "link",
            "content_type",
            "object_id",
            "content_object",
            "is_active",
        ]

    def validate(self, data):
        request = self.context.get("request")

        if request is None:
            raise serializers.ValidationError(
                {
                    "error": (
                        "Request context is required."
                    )
                }
            )

        content_type_key = data.get(
            "content_type"
        )
        object_id = data.get("object_id")
        social_media_type = data.get(
            "social_media_type"
        )
        link = data.get("link")

        content_type = (
            social_content_type_for_key(
                content_type_key
            )
        )

        if content_type is None:
            raise serializers.ValidationError(
                {
                    "error": (
                        "Invalid content_type "
                        "provided."
                    )
                }
            )

        owner = (
            resolve_social_owner_for_management(
                actor=request.user,
                content_type_key=(
                    content_type_key
                ),
                object_id=object_id,
            )
        )

        if owner is None:
            raise serializers.ValidationError(
                {
                    "error": (
                        "You do not have permission "
                        "to add or modify links for "
                        "this object."
                    )
                }
            )

        existing_link = (
            SocialMediaLink.objects
            .filter(
                content_type=content_type,
                object_id=owner.pk,
                social_media_type=(
                    social_media_type
                ),
            )
            .first()
        )

        if existing_link:
            raise serializers.ValidationError(
                {
                    "error": (
                        "A link for this social "
                        "media type already exists."
                    )
                }
            )

        if SocialMediaLink.objects.filter(
            link=link
        ).exists():
            raise serializers.ValidationError(
                {
                    "error": (
                        "This URL is already in use."
                    )
                }
            )

        return data

    def create(self, validated_data):
        content_type_key = (
            validated_data.pop(
                "content_type"
            )
        )
        object_id = validated_data.pop(
            "object_id"
        )

        content_type = (
            social_content_type_for_key(
                content_type_key
            )
        )

        if content_type is None:
            raise serializers.ValidationError(
                {
                    "error": (
                        "Invalid content_type "
                        "provided."
                    )
                }
            )

        validated_data["content_type"] = (
            content_type
        )
        validated_data["object_id"] = (
            object_id
        )

        return super().create(
            validated_data
        )

    def get_content_object(self, obj):
        content_object = obj.content_object

        if isinstance(
            content_object,
            Organization,
        ):
            return {
                "type": "organization",
                "name": content_object.name,
            }

        request = self.context.get("request")

        if (
            request is not None
            and content_object
            == request.user
        ):
            return {
                "type": "user",
                "username": (
                    content_object.username
                ),
            }

        return None


class SocialMediaLinkReadOnlySerializer(
    serializers.ModelSerializer
):
    social_media_type = (
        SocialMediaTypeSerializer(
            read_only=True
        )
    )
    content_object = (
        serializers.SerializerMethodField(
            read_only=True
        )
    )

    class Meta:
        model = SocialMediaLink
        fields = [
            "id",
            "social_media_type",
            "link",
            "content_object",
            "is_active",
        ]

    def get_content_object(self, obj):
        content_object = obj.content_object

        if isinstance(
            content_object,
            Organization,
        ):
            return {
                "type": "organization",
                "name": content_object.name,
            }

        request = self.context.get("request")

        if (
            request is not None
            and content_object
            == request.user
        ):
            return {
                "type": "user",
                "username": (
                    content_object.username
                ),
            }

        return None