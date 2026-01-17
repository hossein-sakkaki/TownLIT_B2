# apps/posts/serializers/testimonies.py

from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
import logging

from apps.posts.models.testimony import Testimony
from apps.core.visibility.constants import VISIBILITY_DEFAULT
from apps.media_conversion.services.serializer_gate import gate_media_payload

from common.file_handlers.media_mixins import (
    AudioFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
)
from common.serializers.targets import InstanceTargetMixin
from apps.core.ownership.utils import resolve_owner_from_request
from .serializers_owner_min import build_owner_dto_from_content_object

logger = logging.getLogger(__name__)


class TestimonySerializer( 
    InstanceTargetMixin,
    AudioFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    """
    Final Testimony serializer (Moment-compatible)

    - Visibility aware
    - Interaction counters exposed
    - Owner-write rules enforced
    - Frontend-safe (no breaking response shape)
    """

    owner = serializers.SerializerMethodField(read_only=True)

    # GFK (read-only)
    content_type = serializers.PrimaryKeyRelatedField(read_only=True)
    object_id = serializers.IntegerField(read_only=True)

    # Moderation flags (read-only)
    is_active = serializers.BooleanField(read_only=True)
    is_suspended = serializers.BooleanField(read_only=True)
    reports_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Testimony
        fields = [
            # identity
            "id",
            "slug",

            # core
            "type",
            "title",
            "content",
            "audio",
            "video",
            "thumbnail",

            # visibility / moderation
            "visibility",
            "is_hidden",
            "is_active",
            "is_suspended",
            "reports_count",

            # interactions (🔥 NEW but backward-safe)
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            # timestamps
            "published_at",
            "updated_at",

            # media
            "is_converted",

            # targets
            "comment_target",
            "reaction_target",

            # ownership
            "content_type",
            "object_id",
            "owner",
        ]

        read_only_fields = [
            "id",
            "slug",
            "published_at",
            "updated_at",
            "is_converted",
            "content_type",
            "object_id",
            "comment_target",
            "reaction_target",
            "owner",

            # moderation
            "is_active",
            "is_suspended",
            "reports_count",
        ]

    # -------------------------------------------------
    # OWNER DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        try:
            request = self.context.get("request")

            # Optional: like Moment, lighter POST response
            if request and request.method == "POST":
                return None

            return build_owner_dto_from_content_object(
                obj,
                context=self.context,
            )
        except Exception:
            logger.exception(
                "🔥🔥🔥🔥get_owner failed for testimony id=%s",
                getattr(obj, "id", None)
            )
            return None

    
    # -------------------------------------------------
    # Ownership helpers
    # -------------------------------------------------
    def _get_request_owner(self):
        request = self.context.get("request")
        if not request:
            return None

        return resolve_owner_from_request(request)


    def _assert_owner(self, instance):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        owner = resolve_owner_from_request(request)
        if not owner:
            raise serializers.ValidationError("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        if (
            instance.content_type_id != owner_ct.id
            or instance.object_id != owner.id
        ):
            raise serializers.ValidationError(
                "You do not have permission to modify this Testimony."
            )


    # -------------------------------------------------
    # CREATE
    # -------------------------------------------------
    def create(self, validated_data):
        """
        - visibility defaults if missing
        - owner is injected by ViewSet
        """
        if "visibility" not in validated_data:
            validated_data["visibility"] = VISIBILITY_DEFAULT

        # safety
        validated_data.pop("is_active", None)
        validated_data.pop("is_suspended", None)
        validated_data.pop("reports_count", None)

        return super().create(validated_data)

    # -------------------------------------------------
    # UPDATE (owner-write rules)
    # -------------------------------------------------
    def update(self, instance, validated_data):
        """
        Owner may update:
        - content fields
        - visibility
        - is_hidden

        Forbidden:
        - moderation flags
        - counters
        - owner
        """
        self._assert_owner(instance)

        forbidden_fields = {
            "content_type",
            "object_id",
            "is_active",
            "is_suspended",
            "reports_count",
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",
        }

        for field in forbidden_fields:
            if field in validated_data:
                raise serializers.ValidationError(
                    f"Field '{field}' cannot be modified."
                )

        return super().update(instance, validated_data)

    # -------------------------------------------------
    # Cross-field validation (business rules)
    # -------------------------------------------------
    def validate(self, attrs):
        
        # ✅ forbid ownership injection (same as Moment)
        forbidden = {"content_type", "object_id"}
        for key in forbidden:
            if key in self.initial_data:
                raise serializers.ValidationError({key: "This field is not allowed."})
        
        instance = self.instance

        ttype = attrs.get("type") or (
            instance.type if instance else self.context.get("ttype")
        )

        title = attrs.get("title") or (instance.title if instance else None)
        content = attrs.get("content") or (instance.content if instance else None)
        audio = attrs.get("audio") or (instance.audio if instance else None)
        video = attrs.get("video") or (instance.video if instance else None)

        if ttype == Testimony.TYPE_WRITTEN:
            if not content or audio or video:
                raise serializers.ValidationError(
                    "Written testimony requires content only."
                )
            if not title or not title.strip():
                raise serializers.ValidationError(
                    {"title": "Title is required."}
                )
            if len(title) > 50:
                raise serializers.ValidationError(
                    {"title": "Max 50 characters."}
                )

        elif ttype == Testimony.TYPE_AUDIO:
            if not audio or content or video:
                raise serializers.ValidationError(
                    "Audio testimony requires audio only."
                )

        elif ttype == Testimony.TYPE_VIDEO:
            if not video or content or audio:
                raise serializers.ValidationError(
                    "Video testimony requires video only."
                )

        else:
            raise serializers.ValidationError("Invalid testimony type.")

        attrs["type"] = ttype
        return attrs

    # -------------------------------------------------
    # MEDIA READINESS GATE (serializer-level)
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        # 🔐 HARD VISIBILITY GATE
        if obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO):
            # If NOT converted → object must be invisible to non-owner
            if not obj.is_converted:
                # Allow ONLY owner to see conversion state
                owner = resolve_owner_from_request(request) if request else None

                if not owner or (
                    obj.content_type_id != ContentType.objects.get_for_model(owner.__class__).id
                    or obj.object_id != owner.id
                ):
                    # 🚫 viewer should NOT see this testimony at all
                    return None

        data = super().to_representation(obj)

        # OWNER ONLY: show conversion panel data
        if obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO):
            data = gate_media_payload(
                obj=obj,
                data=data,
                viewer=viewer,
                field_name="video" if obj.type == Testimony.TYPE_VIDEO else "audio",
                require_job=True,
                include_job_target=True,
            )

        return data
