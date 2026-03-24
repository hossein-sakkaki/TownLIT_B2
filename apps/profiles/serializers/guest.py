# apps/profiles/serializers/guest.py

import logging

from django.utils import timezone
from rest_framework import serializers

from apps.profiles.models.guest import GuestUser
from apps.profiles.helpers.social_links import social_links_for_user
from apps.profiles.friends_priority.service import get_friends_for_profile
from apps.accounts.serializers.user_serializers import (
    CustomUserSerializer,
    PublicCustomUserSerializer,
    LimitedCustomUserSerializer,
    SimpleCustomUserSerializer,
)
from apps.accounts.serializers.social_serializers import SocialMediaLinkReadOnlySerializer

logger = logging.getLogger(__name__)


class FriendsBlockMixin:
    """Reusable friends getter for profile serializers."""

    def _build_friends_payload(self, profile_obj):
        request = self.context.get("request")
        q = getattr(request, "query_params", {}) if request else {}

        random_flag = str(q.get("random", "1")) == "1"
        daily_flag = str(q.get("daily", "0")) == "1"
        seed = q.get("seed")

        try:
            limit = int(q.get("limit")) if q.get("limit") is not None else None
        except (TypeError, ValueError):
            limit = None

        try:
            friends = get_friends_for_profile(
                profile_obj.user,
                random=random_flag,
                daily=daily_flag,
                seed=seed,
                limit=limit,
            )
            return SimpleCustomUserSerializer(
                friends,
                many=True,
                context=self.context,
            ).data
        except Exception:
            logger.exception(
                "friends block failed for guest user_id=%s",
                getattr(profile_obj.user, "id", None),
            )
            return []


class GuestUserSerializer(FriendsBlockMixin, serializers.ModelSerializer):
    user = CustomUserSerializer(context=None)
    friends = serializers.SerializerMethodField()

    class Meta:
        model = GuestUser
        fields = [
            "user",
            "biography",
            "is_privacy",
            "register_date",
            "is_migrated",
            "is_active",
            "friends",
        ]
        read_only_fields = [
            "register_date",
            "is_migrated",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"] = CustomUserSerializer(context=self.context)

    def update(self, instance, validated_data):
        custom_user_data = validated_data.pop("user", None)

        if custom_user_data:
            custom_user_serializer = CustomUserSerializer(
                instance.user,
                data=custom_user_data,
                partial=True,
                context=self.context,
            )
            if custom_user_serializer.is_valid():
                custom_user_serializer.save()
            else:
                raise serializers.ValidationError(
                    {"error": "Custom user update failed. Please check the provided data."}
                )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def validate_biography(self, value):
        # Keep bio short
        if value and len(value) > 2000:
            raise serializers.ValidationError("Biography cannot exceed 2000 characters.")
        return value

    def get_friends(self, obj):
        return self._build_friends_payload(obj)


class PublicGuestUserSerializer(FriendsBlockMixin, serializers.ModelSerializer):
    user = PublicCustomUserSerializer(read_only=True)
    social_links = serializers.SerializerMethodField()
    friends = serializers.SerializerMethodField()

    class Meta:
        model = GuestUser
        fields = [
            "user",
            "biography",
            "is_privacy",
            "register_date",
            "is_active",
            "social_links",
            "friends",
        ]
        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"] = PublicCustomUserSerializer(
            context=self.context,
            read_only=True,
        )

    def get_social_links(self, obj):
        links_qs = social_links_for_user(obj.user)
        return SocialMediaLinkReadOnlySerializer(
            links_qs,
            many=True,
            context=self.context,
        ).data

    def get_friends(self, obj):
        return self._build_friends_payload(obj)


class LimitedGuestUserSerializer(serializers.ModelSerializer):
    """Minimal public profile when privacy is restricted."""

    user = LimitedCustomUserSerializer(read_only=True)

    class Meta:
        model = GuestUser
        fields = [
            "user",
        ]
        read_only_fields = fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"] = LimitedCustomUserSerializer(
            context=self.context,
            read_only=True,
        )


class SimpleGuestUserSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = GuestUser
        fields = ["id", "profile_image", "slug"]
        read_only_fields = ["id", "slug"]

    def get_profile_image(self, obj):
        request = self.context.get("request")
        if obj.user.image_name:
            return (
                request.build_absolute_uri(obj.user.image_name.url)
                if request
                else obj.user.image_name.url
            )
        return None