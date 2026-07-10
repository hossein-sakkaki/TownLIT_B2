# apps/posts/serializers/prayers.py

import logging

from django.conf import settings
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
    Return image/thumbnail asset metadata for iOS/web grids.

    Important:
    - New media uses media_assets[field_name].
    - Old media falls back to the original ImageField/ThumbnailField key.
    - variants are included only when generated.
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


# -------------------------------------------------
# Response serializer
# -------------------------------------------------
class PrayerResponseSerializer(
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    # Thumbnail is optional and may be user-provided or generated.
    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    image_asset = serializers.SerializerMethodField(read_only=True)
    thumbnail_asset = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PrayerResponse
        fields = [
            "id",
            "result_status",
            "response_text",

            # Legacy media fields.
            "image",
            "video",
            "thumbnail",

            # Lightweight media metadata for grids/feed/profile.
            "image_asset",
            "thumbnail_asset",

            "created_at",
            "updated_at",
            "is_converted",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_converted",
            "image_asset",
            "thumbnail_asset",
        ]

    # -------------------------------------------------
    # Asset helpers
    # -------------------------------------------------
    def get_image_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="image",
                fallback_key=getattr(getattr(obj, "image", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_image_asset failed for prayer response id=%s",
                obj.id,
            )
            return None

    def get_thumbnail_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="thumbnail",
                fallback_key=getattr(getattr(obj, "thumbnail", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_thumbnail_asset failed for prayer response id=%s",
                obj.id,
            )
            return None

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def validate(self, attrs):
        """
        Media rules for PrayerResponse:
        - image is required.
        - video is optional.
        - image + video is allowed.
        """
        request = self.context.get("request")

        if request and request.method in ("POST", "PUT", "PATCH"):
            image = attrs.get("image") or getattr(self.instance, "image", None)

            if not image:
                raise serializers.ValidationError({
                    "image": "Response image is required."
                })

        return attrs

    # -------------------------------------------------
    # Representation hardening
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        data = super().to_representation(obj)

        # Conversion-safe payload for response video.
        # Response image remains available because it is required.
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


# -------------------------------------------------
# Full Prayer serializer
# -------------------------------------------------
class PrayerSerializer(
    InstanceTargetMixin,
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    owner = serializers.SerializerMethodField(read_only=True)
    response = PrayerResponseSerializer(read_only=True)

    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    image_asset = serializers.SerializerMethodField(read_only=True)
    thumbnail_asset = serializers.SerializerMethodField(read_only=True)

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

            # Content / media.
            "caption",
            "image",
            "video",
            "thumbnail",

            # Lightweight media metadata.
            "image_asset",
            "thumbnail_asset",

            # Lifecycle.
            "status",
            "answered_at",
            "is_waiting",
            "is_completed",

            # Visibility / UI.
            "visibility",
            "is_hidden",

            # Counters.
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            # Timestamps.
            "published_at",
            "updated_at",

            # Pipeline.
            "is_converted",

            # Interaction targets.
            "comment_target",
            "reaction_target",

            # Asset delivery targets.
            "prayer_target",
            "response_target",

            # Ownership.
            "owner",

            # Nested response.
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

            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            "image_asset",
            "thumbnail_asset",
            "prayer_target",
            "response_target",
        ]

    # -------------------------------------------------
    # Computed state
    # -------------------------------------------------
    def get_is_waiting(self, obj):
        return obj.status == PrayerStatus.WAITING

    def get_is_completed(self, obj):
        return obj.status in (
            PrayerStatus.ANSWERED,
            PrayerStatus.NOT_ANSWERED,
        )

    # -------------------------------------------------
    # Asset helpers
    # -------------------------------------------------
    def get_image_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="image",
                fallback_key=getattr(getattr(obj, "image", None), "name", None),
            )
        except Exception:
            logger.exception("get_image_asset failed for prayer id=%s", obj.id)
            return None

    def get_thumbnail_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="thumbnail",
                fallback_key=getattr(getattr(obj, "thumbnail", None), "name", None),
            )
        except Exception:
            logger.exception("get_thumbnail_asset failed for prayer id=%s", obj.id)
            return None

    # -------------------------------------------------
    # Owner DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        OwnerDTO, visitor-hardened.
        """
        try:
            request = self.context.get("request")

            if request and request.method == "POST":
                return None

            owner = build_owner_dto_from_content_object(
                obj,
                context=self.context,
            )

            if not owner:
                return None

            is_authenticated = (
                request
                and request.user
                and request.user.is_authenticated
            )

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
            raise serializers.ValidationError("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        if (
            instance.content_type_id != owner_ct.id
            or instance.object_id != owner.id
        ):
            raise serializers.ValidationError(
                "You do not have permission to modify this Prayer."
            )

    # -------------------------------------------------
    # Create / Update
    # -------------------------------------------------
    def create(self, validated_data):
        validated_data.setdefault("visibility", VISIBILITY_GLOBAL)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._assert_owner(instance)

        forbidden_fields = {
            "content_type",
            "object_id",
            "is_active",
            "is_suspended",
            "reports_count",
        }

        for field in forbidden_fields:
            if field in validated_data:
                raise serializers.ValidationError(
                    f"Field '{field}' cannot be modified."
                )

        return super().update(instance, validated_data)

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def validate(self, attrs):
        request = self.context.get("request")

        if request and request.method in ("POST", "PUT", "PATCH"):
            forbidden = {"content_type", "object_id"}

            for key in forbidden:
                if key in self.initial_data:
                    raise serializers.ValidationError({
                        key: "This field is not allowed."
                    })

            image = attrs.get("image") or getattr(self.instance, "image", None)

            if not image:
                raise serializers.ValidationError(
                    "Prayer must include an image."
                )

        return attrs

    # -------------------------------------------------
    # Representation hardening
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        # Hard gate: visitors cannot see unconverted prayer video.
        if obj.video and not obj.is_converted:
            owner = resolve_owner_from_request(request) if request else None

            if not owner or (
                obj.content_type_id
                != ContentType.objects.get_for_model(owner.__class__).id
                or obj.object_id != owner.id
            ):
                return None

        data = super().to_representation(obj)

        # Conversion-safe payload for prayer video.
        # Prayer image remains available because image is required.
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

        if not viewer:
            data.pop("visibility", None)
            data.pop("is_hidden", None)
            data.pop("reactions_breakdown", None)

        return data

    # -------------------------------------------------
    # Asset delivery targets
    # -------------------------------------------------
    def get_prayer_target(self, obj):
        try:
            ct = ContentType.objects.get_for_model(obj.__class__)
            return {
                "content_type_id": ct.id,
                "object_id": obj.pk,
            }
        except Exception:
            return None

    def get_response_target(self, obj):
        try:
            response = getattr(obj, "response", None)

            if not response:
                return None

            ct = ContentType.objects.get_for_model(response.__class__)

            return {
                "content_type_id": ct.id,
                "object_id": response.pk,
            }
        except Exception:
            return None


# -------------------------------------------------
# Lightweight response serializer for profile grid
# -------------------------------------------------
class PrayerResponseProfileGridSerializer(serializers.ModelSerializer):
    """
    Lightweight response serializer for profile Prayer grid.

    Includes image/thumbnail assets for fast profile grid rendering while
    preserving legacy fallback compatibility.
    """

    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    image_asset = serializers.SerializerMethodField(read_only=True)
    thumbnail_asset = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PrayerResponse
        fields = [
            "id",
            "result_status",

            # Legacy media fields.
            "image",
            "video",
            "thumbnail",

            # Lightweight media metadata.
            "image_asset",
            "thumbnail_asset",

            "is_converted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_image_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="image",
                fallback_key=getattr(getattr(obj, "image", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_image_asset failed for profile grid prayer response id=%s",
                obj.id,
            )
            return None

    def get_thumbnail_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="thumbnail",
                fallback_key=getattr(getattr(obj, "thumbnail", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_thumbnail_asset failed for profile grid prayer response id=%s",
                obj.id,
            )
            return None

    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        data = super().to_representation(obj)

        # Conversion-safe payload for response video.
        # Response image remains available.
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


# -------------------------------------------------
# Lightweight Prayer serializer for profile grid
# -------------------------------------------------
class PrayerProfileGridSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for profile Prayer grid.

    Used by /posts/prayers/me/.
    Includes enough media metadata for:
    - prayer image preview
    - prayer video thumbnail preview
    - response image preview
    - response video thumbnail preview
    - legacy-safe fallback
    """

    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    image_asset = serializers.SerializerMethodField(read_only=True)
    thumbnail_asset = serializers.SerializerMethodField(read_only=True)

    response = PrayerResponseProfileGridSerializer(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Prayer
        fields = [
            "id",
            "slug",

            # Legacy media fields.
            "image",
            "video",
            "thumbnail",

            # Lightweight media metadata.
            "image_asset",
            "thumbnail_asset",

            # Lifecycle.
            "status",
            "answered_at",

            # Visibility / UI.
            "visibility",
            "is_hidden",

            # Pipeline.
            "is_converted",

            # Timestamps.
            "published_at",
            "updated_at",

            # Owner action menu support.
            "owner",

            # Nested lightweight response.
            "response",
        ]
        read_only_fields = fields

    # -------------------------------------------------
    # Asset helpers
    # -------------------------------------------------
    def get_image_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="image",
                fallback_key=getattr(getattr(obj, "image", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_image_asset failed for profile grid prayer id=%s",
                obj.id,
            )
            return None

    def get_thumbnail_asset(self, obj):
        try:
            return _image_asset_payload(
                obj=obj,
                field_name="thumbnail",
                fallback_key=getattr(getattr(obj, "thumbnail", None), "name", None),
            )
        except Exception:
            logger.exception(
                "get_thumbnail_asset failed for profile grid prayer id=%s",
                obj.id,
            )
            return None

    # -------------------------------------------------
    # Owner DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        Minimal owner payload for profile grid.
        """
        try:
            request = self.context.get("request")
            owner = resolve_owner_from_request(request) if request else None

            is_me = False

            if owner:
                owner_ct = ContentType.objects.get_for_model(owner.__class__)
                is_me = (
                    obj.content_type_id == owner_ct.id
                    and obj.object_id == owner.id
                )

            return {
                "type": "current",
                "id": obj.object_id,
                "is_me": bool(is_me),
            }

        except Exception:
            logger.exception(
                "get_owner failed for profile grid prayer id=%s",
                obj.id,
            )
            return {
                "type": "current",
                "id": getattr(obj, "object_id", None),
                "is_me": False,
            }

    # -------------------------------------------------
    # Representation hardening
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        data = super().to_representation(obj)

        # Conversion-safe payload for main prayer video.
        # Prayer image remains available because image is required.
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
    
    
    
# -------------------------------------------------
# Lightweight response serializer for Stream payload
# -------------------------------------------------
class PrayerResponseStreamPayloadSerializer(serializers.ModelSerializer):
    """
    Ultra-light PrayerResponse serializer for Stream endpoint only.
    """

    image = serializers.SerializerMethodField(read_only=True)
    video = serializers.SerializerMethodField(read_only=True)
    thumbnail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PrayerResponse
        fields = [
            "id",
            "result_status",
            "response_text",
            "image",
            "video",
            "thumbnail",
            "is_converted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_image(self, obj):
        return self._safe_cdn_for_field(
            obj=obj,
            field_name="image",
        )

    def get_video(self, obj):
        return self._safe_key_for_field(
            obj=obj,
            field_name="video",
        )

    def get_thumbnail(self, obj):
        return self._safe_cdn_for_field(
            obj=obj,
            field_name="thumbnail",
        )

    def _safe_key_for_field(
        self,
        *,
        obj,
        field_name: str,
    ) -> str | None:
        asset = _media_asset(obj, field_name)
        key = _clean_asset_key(asset.get("key"))

        if key:
            return key

        value = getattr(obj, field_name, None)
        return _clean_asset_key(value)

    def _safe_cdn_for_field(
        self,
        *,
        obj,
        field_name: str,
    ) -> str | None:
        key = self._safe_key_for_field(
            obj=obj,
            field_name=field_name,
        )

        return _build_asset_cdn_url(key)


# -------------------------------------------------
# Lightweight Prayer serializer for Stream payload
# -------------------------------------------------
class PrayerStreamPayloadSerializer(
    InstanceTargetMixin,
    serializers.ModelSerializer,
):
    """
    Ultra-light Prayer serializer for Stream endpoint only.

    StreamItemSerializer adds:
    - preview
    - response preview
    - owner
    - boundary metadata
    """

    image = serializers.SerializerMethodField(read_only=True)
    video = serializers.SerializerMethodField(read_only=True)
    thumbnail = serializers.SerializerMethodField(read_only=True)
    response = PrayerResponseStreamPayloadSerializer(read_only=True)

    class Meta:
        model = Prayer
        fields = [
            "id",
            "slug",

            # Content / media.
            "caption",
            "image",
            "video",
            "thumbnail",

            # Lifecycle.
            "status",
            "answered_at",

            # Visibility / UI.
            "visibility",
            "is_hidden",

            # Counters.
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",

            # Timestamps.
            "published_at",
            "updated_at",

            # Pipeline.
            "is_converted",

            # Interaction targets.
            "comment_target",
            "reaction_target",

            # Nested lightweight response.
            "response",
        ]

        read_only_fields = fields

    def get_image(self, obj):
        return self._safe_cdn_for_field(
            obj=obj,
            field_name="image",
        )

    def get_video(self, obj):
        return self._safe_key_for_field(
            obj=obj,
            field_name="video",
        )

    def get_thumbnail(self, obj):
        return self._safe_cdn_for_field(
            obj=obj,
            field_name="thumbnail",
        )

    def _safe_key_for_field(
        self,
        *,
        obj,
        field_name: str,
    ) -> str | None:
        asset = _media_asset(obj, field_name)
        key = _clean_asset_key(asset.get("key"))

        if key:
            return key

        value = getattr(obj, field_name, None)
        return _clean_asset_key(value)

    def _safe_cdn_for_field(
        self,
        *,
        obj,
        field_name: str,
    ) -> str | None:
        key = self._safe_key_for_field(
            obj=obj,
            field_name=field_name,
        )

        return _build_asset_cdn_url(key)