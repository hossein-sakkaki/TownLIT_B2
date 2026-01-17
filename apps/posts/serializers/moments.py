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
from apps.posts.serializers.common import FilterNoneListSerializer
from .serializers_owner_min import build_owner_dto_from_content_object
from apps.media_conversion.services.serializer_gate import gate_media_payload
from apps.core.ownership.utils import resolve_owner_from_request

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

    # thumbnail is generated automatically during video conversion
    # DO NOT require thumbnail on upload for Moment
    thumbnail = serializers.ImageField(required=False, allow_null=True, use_url=True)

    class Meta:
        model = Moment
        list_serializer_class = FilterNoneListSerializer
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

            # counters should never be writable
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",
        ]

    # -------------------------------------------------
    # Owner DTO (FINAL)
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        Returns OwnerDTO (public or full) or None
        """
        try:
            request = self.context.get("request")

            # Skip owner during POST response
            if request and request.method == "POST":
                return None

            owner = build_owner_dto_from_content_object(
                obj,
                context=self.context,
            )

            if not owner:
                return None

            # ---------------------------------------------
            # Visitor-safe owner hardening
            # ---------------------------------------------
            is_authenticated = (
                request
                and request.user
                and request.user.is_authenticated
            )

            if not is_authenticated:
                # Strip sensitive/internal fields for visitors
                owner.pop("email", None)
                owner.pop("mobile_number", None)
                owner.pop("last_seen", None)
                owner.pop("is_online", None)
                owner.pop("internal_roles", None)
                owner.pop("permissions", None)

            logger.debug("Moment owner dto=%s", owner)
            return owner

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
        request = self.context.get("request")

        # Only enforce on write
        if request and request.method in ("POST", "PUT", "PATCH"):
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


    # -------------------------------------------------
    # Representation hardening (SAFE)
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        # -------------------------------------------------
        # 🔐 HARD MEDIA VISIBILITY GATE (Moment)
        # -------------------------------------------------
        if obj.video and not obj.is_converted:
            owner = resolve_owner_from_request(request) if request else None

            # 🚫 visitor: completely invisible
            if not owner or (
                obj.content_type_id
                != ContentType.objects.get_for_model(owner.__class__).id
                or obj.object_id != owner.id
            ):
                return None

        # 👇 IMPORTANT: do NOT return None for owner
        data = super().to_representation(obj)

        # -------------------------------------------------
        # 🧠 OWNER conversion-safe payload
        # -------------------------------------------------
        if obj.video and not obj.is_converted:
            # 1) strip unsafe media fields
            data["video"] = None
            data["thumbnail"] = None

            # 2) attach conversion job metadata
            data = gate_media_payload(
                obj=obj,
                data=data,
                viewer=viewer,
                field_name="video",
                require_job=True,
                include_job_target=True,
            )

        # -------------------------------------------------
        # Visitor hardening
        # -------------------------------------------------
        if not viewer:
            data.pop("visibility", None)
            data.pop("is_hidden", None)
            data.pop("reactions_breakdown", None)

        return data
