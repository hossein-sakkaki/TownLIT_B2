# apps/posts/serializers/testimonies.py

from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
import logging

from apps.profiles.models.member import Member
from apps.posts.models.testimony import Testimony
from apps.subtitles.models import VideoTranscript, TranscriptJobStatus
from apps.core.visibility.constants import VISIBILITY_GLOBAL
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

    transcript_id = serializers.SerializerMethodField(read_only=True)
    transcript_language = serializers.SerializerMethodField(read_only=True)
    has_transcript = serializers.SerializerMethodField(read_only=True)

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

            # transcript
            "has_transcript",
            "transcript_id",
            "transcript_language",

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
            "view_count_internal",

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
        """
        Testimony is Member-only.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        return getattr(request.user, "member_profile", None)


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
            validated_data["visibility"] = VISIBILITY_GLOBAL

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
                owner = getattr(request.user, "member_profile", None) if request and request.user.is_authenticated else None

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

    # -------------------------------------------------
    # Transcript / subtitles helpers
    # -------------------------------------------------
    def _get_transcript(self, obj):
        """
        Return VideoTranscript if exists and DONE.
        Cached per serializer instance to avoid N+1.
        """
        if not hasattr(self, "_transcript_cache"):
            ct = ContentType.objects.get_for_model(obj.__class__)
            self._transcript_cache = VideoTranscript.objects.filter(
                content_type=ct,
                object_id=obj.id,
                status=TranscriptJobStatus.DONE,
            ).first()
        return self._transcript_cache


    def get_has_transcript(self, obj):
        return self._get_transcript(obj) is not None


    def get_transcript_id(self, obj):
        tr = self._get_transcript(obj)
        return tr.id if tr else None


    def get_transcript_language(self, obj):
        tr = self._get_transcript(obj)
        return tr.source_language if tr else None


# -------------------------------------------------
# Profile header serializer
# -------------------------------------------------
class TestimonyProfileHeaderSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for profile testimony header/carousel.

    Used by /posts/testimonies/me/ and /posts/testimonies/summary/.

    Testimony is Member-only, so owner detection is based directly on
    request.user.member_profile.
    """

    owner = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Testimony
        fields = [
            "id",
            "slug",

            # Core
            "type",
            "title",
            "content",

            # Media
            "audio",
            "video",
            "thumbnail",

            # Visibility / UI
            "visibility",
            "is_hidden",

            # Timestamps / pipeline
            "published_at",
            "updated_at",
            "is_converted",

            # Owner action menu support
            "owner",
        ]
        read_only_fields = fields

    # -------------------------------------------------
    # Owner DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        Minimal owner payload for current user's testimony UI.
        """
        try:
            request = self.context.get("request")

            member = (
                getattr(request.user, "member_profile", None)
                if request and request.user.is_authenticated
                else None
            )

            member_ct = ContentType.objects.get_for_model(
                Member,
                for_concrete_model=False,
            )

            is_me = bool(
                member
                and obj.content_type_id == member_ct.id
                and obj.object_id == member.id
            )

            return {
                "type": "member",
                "id": obj.object_id,
                "is_me": is_me,
            }

        except Exception:
            logger.exception(
                "get_owner failed for profile header testimony id=%s",
                getattr(obj, "id", None),
            )
            return {
                "type": "member",
                "id": getattr(obj, "object_id", None),
                "is_me": False,
            }

    # -------------------------------------------------
    # Representation hardening
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        # Owner can see converting audio/video for progress UI.
        # Non-owner should never receive unconverted media.
        if obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO) and not obj.is_converted:
            member = (
                getattr(request.user, "member_profile", None)
                if request and request.user.is_authenticated
                else None
            )

            member_ct = ContentType.objects.get_for_model(
                Member,
                for_concrete_model=False,
            )

            is_owner = bool(
                member
                and obj.content_type_id == member_ct.id
                and obj.object_id == member.id
            )

            if not is_owner:
                return None

        data = super().to_representation(obj)

        # Include conversion panel payload only while processing.
        if obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO) and not obj.is_converted:
            data = gate_media_payload(
                obj=obj,
                data=data,
                viewer=viewer,
                field_name="video" if obj.type == Testimony.TYPE_VIDEO else "audio",
                require_job=True,
                include_job_target=True,
            )

        return data