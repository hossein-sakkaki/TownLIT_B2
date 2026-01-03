# apps/posts/serializers/moments.py
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from apps.posts.models.moment import Moment
from apps.core.visibility.constants import VISIBILITY_DEFAULT
from common.serializers.targets import InstanceTargetMixin
from common.file_handlers.media_mixins import (
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
)
from .serializers_owner_min import build_owner_dto_from_content_object
import logging
logger = logging.getLogger(__name__)

class MomentSerializer(
    InstanceTargetMixin,
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    owner = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Moment
        fields = [
            "id",
            "slug",

            # content
            "caption",
            "image",
            "video",
            "thumbnail",

            # visibility / UI
            "visibility",
            "is_hidden",

            # interaction counters
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            # timestamps
            "published_at",
            "updated_at",

            # media pipeline
            "is_converted",

            # interaction
            "comment_target",
            "reaction_target",

            # ownership
            "owner",
        ]

        read_only_fields = [
            "id",
            "slug",
            "published_at",
            "updated_at",
            "is_converted",
            "comment_target",
            "reaction_target",
            "owner",
        ]

    # -------------------------------------------------
    # Owner DTO (FINAL)
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        Returns OwnerDTO or None
        """
        try:
            request = self.context.get("request")

            # Avoid redundant owner during POST response if needed
            if request and request.method == "POST":
                return None

            owner = build_owner_dto_from_content_object(
                obj,
                context=self.context,
            )

            logger.debug("Moment owner dto=%s", owner)
            return owner  # ← None is valid

        except Exception:
            logger.exception("🔥 get_owner failed for moment id=%s", obj.id)
            return None

    # -------------------------------------------------
    # Ownership helpers
    # -------------------------------------------------
    def _get_request_owner(self):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        user = request.user

        if hasattr(user, "member_profile"):
            return user.member_profile

        if hasattr(user, "guest_profile"):
            return user.guest_profile

        return None


    def _assert_owner(self, instance):
        owner = self._get_request_owner()
        if not owner:
            raise serializers.ValidationError(
                "Invalid owner context."
            )

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        if (
            instance.content_type_id != owner_ct.id
            or instance.object_id != owner.id
        ):
            raise serializers.ValidationError(
                "You do not have permission to modify this Moment."
            )

    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    def create(self, validated_data):
        """
        Owner is resolved by ViewSet.
        Serializer enforces defaults + guards.
        """
        validated_data.setdefault(
            "visibility",
            VISIBILITY_DEFAULT,
        )

        return super().create(validated_data)

    # -------------------------------------------------
    # Update (owner-write rules)
    # -------------------------------------------------
    def update(self, instance, validated_data):
        self._assert_owner(instance)

        forbidden_fields = {
            "is_active",
            "is_suspended",
            "reports_count",
            "content_type",
            "object_id",
        }

        for field in forbidden_fields:
            if field in validated_data:
                raise serializers.ValidationError(
                    f"Field '{field}' cannot be modified."
                )

        return super().update(instance, validated_data)

    # -------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------
    def validate(self, attrs):
        # -------------------------------------------------
        # Defensive guard: forbid ownership injection
        # -------------------------------------------------
        forbidden = {"content_type", "object_id"}
        for key in forbidden:
            if key in self.initial_data:
                raise serializers.ValidationError({
                    key: "This field is not allowed."
                })

        # -------------------------------------------------
        # Cross-field media validation
        # -------------------------------------------------
        image = attrs.get("image") or getattr(self.instance, "image", None)
        video = attrs.get("video") or getattr(self.instance, "video", None)

        if image and video:
            raise serializers.ValidationError(
                "Moment cannot contain both image and video."
            )

        if not image and not video:
            raise serializers.ValidationError(
                "Moment must contain either an image or a video."
            )

        return attrs

