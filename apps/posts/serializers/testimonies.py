# apps/posts/serializers/testimonies.py

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
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


# -------------------------------------------------
# Asset helpers
# -------------------------------------------------
def _build_asset_cdn_url(key: str | None) -> str | None:
    """
    Build lightweight CDN URL for stored media keys.
    """
    if not key:
        return None

    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")
    if not base:
        return None

    return f"{base}/{str(key).lstrip('/')}"


def _clean_asset_key(value) -> str | None:
    if not value:
        return None

    raw = getattr(value, "name", value)

    if not raw:
        return None

    cleaned = str(raw).strip().lstrip("/")
    return cleaned or None


def _media_asset(obj, field_name: str) -> dict:
    assets = getattr(obj, "media_assets", None) or {}

    if not isinstance(assets, dict):
        return {}

    value = assets.get(field_name)
    return value if isinstance(value, dict) else {}


def _media_dimensions(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {
            "width": None,
            "height": None,
            "aspect_ratio": None,
        }

    return {
        "width": payload.get("width"),
        "height": payload.get("height"),
        "aspect_ratio": payload.get("aspect_ratio"),
    }


def _variants_payload(variants: dict | None) -> dict:
    if not isinstance(variants, dict):
        return {}

    output = {}

    for name, payload in variants.items():
        if not isinstance(payload, dict):
            continue

        key = _clean_asset_key(payload.get("key"))
        url = _build_asset_cdn_url(key)

        output[name] = {
            **payload,
            "key": key,
            "cdn_url": url,
            "image_url": url,
            "url": url,
        }

    return output


def _image_asset_payload(
    *,
    obj,
    field_name: str,
    fallback_key: str | None = None,
) -> dict | None:
    """
    Return thumbnail/image-like asset metadata.

    For Testimony we intentionally keep this minimal:
    - thumbnail_asset is the only profile/media preview asset needed.
    - old testimonies fall back to obj.thumbnail.name.
    """
    asset = _media_asset(obj, field_name)
    key = _clean_asset_key(asset.get("key")) or _clean_asset_key(fallback_key)

    if not key:
        return None

    url = _build_asset_cdn_url(key)

    return {
        **asset,
        "key": key,
        "cdn_url": url,
        "image_url": url,
        "url": url,
        "variants": _variants_payload(asset.get("variants")),
        **_media_dimensions(asset),
    }


class TestimonySerializer(
    InstanceTargetMixin,
    AudioFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    """
    Final Testimony serializer.

    - Visibility aware
    - Interaction counters exposed
    - Owner-write rules enforced
    - Conversion-safe
    - Thumbnail asset exposed for fast grid/profile rendering
    """

    owner = serializers.SerializerMethodField(read_only=True)

    # GFK read-only.
    content_type = serializers.PrimaryKeyRelatedField(read_only=True)
    object_id = serializers.IntegerField(read_only=True)

    # Moderation flags read-only.
    is_active = serializers.BooleanField(read_only=True)
    is_suspended = serializers.BooleanField(read_only=True)
    reports_count = serializers.IntegerField(read_only=True)

    transcript_id = serializers.SerializerMethodField(read_only=True)
    transcript_language = serializers.SerializerMethodField(read_only=True)
    has_transcript = serializers.SerializerMethodField(read_only=True)

    thumbnail_asset = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Testimony
        fields = [
            # Identity.
            "id",
            "slug",

            # Core.
            "type",
            "title",
            "content",
            "audio",
            "video",
            "thumbnail",

            # Lightweight media metadata.
            "thumbnail_asset",

            # Visibility / moderation.
            "visibility",
            "is_hidden",
            "is_active",
            "is_suspended",
            "reports_count",

            # Interactions.
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            # Timestamps.
            "published_at",
            "updated_at",

            # Media.
            "is_converted",

            # Transcript.
            "has_transcript",
            "transcript_id",
            "transcript_language",

            # Targets.
            "comment_target",
            "reaction_target",

            # Ownership.
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

            # Moderation.
            "is_active",
            "is_suspended",
            "reports_count",

            # Lightweight media metadata.
            "thumbnail_asset",
        ]

    # -------------------------------------------------
    # Asset helpers
    # -------------------------------------------------
    def get_thumbnail_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="thumbnail",
                fallback_key=getattr(getattr(obj, "thumbnail", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_thumbnail_asset failed for testimony id=%s",
                getattr(obj, "id", None),
            )
            return None

    # -------------------------------------------------
    # Owner DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        try:
            request = self.context.get("request")

            if request and request.method == "POST":
                return None

            return build_owner_dto_from_content_object(
                obj,
                context=self.context,
            )
        except Exception:
            logger.exception(
                "get_owner failed for testimony id=%s",
                getattr(obj, "id", None),
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
    # Create
    # -------------------------------------------------
    def create(self, validated_data):
        if "visibility" not in validated_data:
            validated_data["visibility"] = VISIBILITY_GLOBAL

        validated_data.pop("is_active", None)
        validated_data.pop("is_suspended", None)
        validated_data.pop("reports_count", None)

        return super().create(validated_data)

    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def update(self, instance, validated_data):
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
    # Cross-field validation
    # -------------------------------------------------
    def validate(self, attrs):
        forbidden = {"content_type", "object_id"}

        for key in forbidden:
            if key in self.initial_data:
                raise serializers.ValidationError({
                    key: "This field is not allowed."
                })

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
                raise serializers.ValidationError({
                    "title": "Title is required."
                })

            if len(title) > 50:
                raise serializers.ValidationError({
                    "title": "Max 50 characters."
                })

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
    # Media readiness gate
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        if obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO):
            if not obj.is_converted:
                owner = (
                    getattr(request.user, "member_profile", None)
                    if request and request.user.is_authenticated
                    else None
                )

                if not owner or (
                    obj.content_type_id
                    != ContentType.objects.get_for_model(owner.__class__).id
                    or obj.object_id != owner.id
                ):
                    return None

        data = super().to_representation(obj)

        # Owner-only conversion payload for audio/video.
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
        Cached per serializer instance to avoid N+1 for single-object usage.
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
        transcript = self._get_transcript(obj)
        return transcript.id if transcript else None

    def get_transcript_language(self, obj):
        transcript = self._get_transcript(obj)
        return transcript.source_language if transcript else None


# -------------------------------------------------
# Profile header serializer
# -------------------------------------------------
class TestimonyProfileHeaderSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for profile testimony header/carousel.

    Used by /posts/testimonies/me/ and /posts/testimonies/summary/.

    Testimony cover/thumbnail is already square-cropped on iOS, so the
    profile contract remains intentionally simple:
    - thumbnail
    - thumbnail_asset
    """

    owner = serializers.SerializerMethodField(read_only=True)
    thumbnail_asset = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Testimony
        fields = [
            "id",
            "slug",

            # Core.
            "type",
            "title",
            "content",

            # Media.
            "audio",
            "video",
            "thumbnail",
            "thumbnail_asset",

            # Visibility / UI.
            "visibility",
            "is_hidden",

            # Timestamps / pipeline.
            "published_at",
            "updated_at",
            "is_converted",

            # Owner action menu support.
            "owner",
        ]
        read_only_fields = fields

    # -------------------------------------------------
    # Asset helpers
    # -------------------------------------------------
    def get_thumbnail_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="thumbnail",
                fallback_key=getattr(getattr(obj, "thumbnail", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_thumbnail_asset failed for profile header testimony id=%s",
                getattr(obj, "id", None),
            )
            return None

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
        if (
            obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO)
            and not obj.is_converted
        ):
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
        if (
            obj.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO)
            and not obj.is_converted
        ):
            data = gate_media_payload(
                obj=obj,
                data=data,
                viewer=viewer,
                field_name="video" if obj.type == Testimony.TYPE_VIDEO else "audio",
                require_job=True,
                include_job_target=True,
            )

        return data