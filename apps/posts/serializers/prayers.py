# apps/posts/serializers/prayers.py

import logging

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.posts.models.pray import Prayer, PrayerResponse, PrayerStatus
from apps.core.visibility.constants import VISIBILITY_GLOBAL
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


logger = logging.getLogger(__name__)


class PrayerResponseSerializer(
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    # Thumbnail is optional (user-provided)
    thumbnail = serializers.ImageField(required=False, allow_null=True, use_url=True)

    class Meta:
        model = PrayerResponse
        fields = [
            "id",
            "result_status",
            "response_text",
            "image",
            "video",
            "thumbnail",
            "created_at",
            "updated_at",
            "is_converted",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_converted",
        ]

    def validate(self, attrs):
        """
        Media rules (Response):
        - image is required (always)
        - video is optional
        - image + video is allowed
        """
        request = self.context.get("request")
        if request and request.method in ("POST", "PUT", "PATCH"):
            image = attrs.get("image") or getattr(self.instance, "image", None)

            # Image is required
            if not image:
                raise serializers.ValidationError({"image": "Response image is required."})

            # No XOR check anymore

        return attrs

    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        data = super().to_representation(obj)

        # Conversion-safe payload (response video)
        if obj.video and not obj.is_converted:
            data["video"] = None
            data["thumbnail"] = None
            data = gate_media_payload(
                obj=obj,
                data=data,
                viewer=viewer,
                field_name="video",
                require_job=True,
                include_job_target=True,
            )

        return data


class PrayerSerializer(
    InstanceTargetMixin,
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    owner = serializers.SerializerMethodField(read_only=True)
    response = PrayerResponseSerializer(read_only=True)

    # Thumbnail optional (user-provided)
    thumbnail = serializers.ImageField(required=False, allow_null=True, use_url=True)

    is_waiting = serializers.SerializerMethodField(read_only=True)
    is_completed = serializers.SerializerMethodField(read_only=True)

    prayer_target = serializers.SerializerMethodField(read_only=True)
    response_target = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Prayer
        list_serializer_class = FilterNoneListSerializer
        fields = [
            "id",
            "slug",

            # content
            "caption",
            "image",
            "video",
            "thumbnail",

            # lifecycle
            "status",
            "answered_at",
            "is_waiting",
            "is_completed",

            # visibility / UI
            "visibility",
            "is_hidden",

            # counters
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            # timestamps
            "published_at",
            "updated_at",

            # pipeline
            "is_converted",

            # interaction targets
            "comment_target",
            "reaction_target",

            # ✅ asset delivery targets
            "prayer_target",
            "response_target",
            
            # ownership
            "owner",

            # nested response
            "response",
            
        ]

        read_only_fields = [
            "id",
            "slug",
            "published_at",
            "updated_at",
            "is_converted",
            "answered_at",
            "comment_target",
            "reaction_target",
            "owner",
            "response",
            "is_waiting",
            "is_completed",

            # counters
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",
            "view_count_internal",

            "prayer_target",
            "response_target",
        ]

    def get_is_waiting(self, obj):
        return obj.status == PrayerStatus.WAITING

    def get_is_completed(self, obj):
        return obj.status in (PrayerStatus.ANSWERED, PrayerStatus.NOT_ANSWERED)

    def get_owner(self, obj):
        """OwnerDTO (visitor-hardened)."""
        try:
            request = self.context.get("request")

            # Skip owner in POST response (optional optimization)
            if request and request.method == "POST":
                return None

            owner = build_owner_dto_from_content_object(obj, context=self.context)
            if not owner:
                return None

            # Visitor hardening
            is_authenticated = request and request.user and request.user.is_authenticated
            if not is_authenticated:
                owner.pop("email", None)
                owner.pop("mobile_number", None)
                owner.pop("last_seen", None)
                owner.pop("is_online", None)
                owner.pop("internal_roles", None)
                owner.pop("permissions", None)

            return owner

        except Exception:
            logger.exception("get_owner failed for prayer id=%s", obj.id)
            return None

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
            raise serializers.ValidationError("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        if instance.content_type_id != owner_ct.id or instance.object_id != owner.id:
            raise serializers.ValidationError("You do not have permission to modify this Prayer.")

    def create(self, validated_data):
        """Default visibility on create."""
        validated_data.setdefault("visibility", VISIBILITY_GLOBAL)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Owner-only update rule."""
        self._assert_owner(instance)

        forbidden_fields = {"content_type", "object_id", "is_active", "is_suspended", "reports_count"}
        for f in forbidden_fields:
            if f in validated_data:
                raise serializers.ValidationError(f"Field '{f}' cannot be modified.")

        return super().update(instance, validated_data)

    def validate(self, attrs):
        request = self.context.get("request")

        if request and request.method in ("POST", "PUT", "PATCH"):

            # Ownership injection guard
            forbidden = {"content_type", "object_id"}
            for key in forbidden:
                if key in self.initial_data:
                    raise serializers.ValidationError({key: "This field is not allowed."})

            image = attrs.get("image") or getattr(self.instance, "image", None)

            if not image:
                raise serializers.ValidationError("Prayer must include an image.")

            # ✅ video is optional — no XOR check anymore

        return attrs

    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        # Hard gate: visitors cannot see unconverted prayer video
        if obj.video and not obj.is_converted:
            owner = resolve_owner_from_request(request) if request else None
            if not owner or (
                obj.content_type_id != ContentType.objects.get_for_model(owner.__class__).id
                or obj.object_id != owner.id
            ):
                return None

        data = super().to_representation(obj)

        # Conversion-safe payload (prayer video)
        if obj.video and not obj.is_converted:
            data["video"] = None
            data["thumbnail"] = None
            data = gate_media_payload(
                obj=obj,
                data=data,
                viewer=viewer,
                field_name="video",
                require_job=True,
                include_job_target=True,
            )

        # Visitor stripping
        if not viewer:
            data.pop("visibility", None)
            data.pop("is_hidden", None)
            data.pop("reactions_breakdown", None)

        return data
    
    def get_prayer_target(self, obj):
        """
        Asset-delivery target for the MAIN prayer object.
        Always exists.
        """
        try:
            ct = ContentType.objects.get_for_model(obj.__class__)
            return {
                "content_type_id": ct.id,
                "object_id": obj.pk,
            }
        except Exception:
            return None

    def get_response_target(self, obj):
        """
        Asset-delivery target for the RESPONSE object.
        Only exists when obj.response exists.
        """
        try:
            r = getattr(obj, "response", None)
            if not r:
                return None
            ct = ContentType.objects.get_for_model(r.__class__)
            return {
                "content_type_id": ct.id,
                "object_id": r.pk,
            }
        except Exception:
            return None