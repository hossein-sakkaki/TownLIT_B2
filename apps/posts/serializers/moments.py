# apps/posts/serializers/moments.py

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction
from django.conf import settings
from rest_framework import serializers

from apps.posts.models.moment import Moment
from apps.posts.constants.moments import (
    MOMENT_MEDIA_KIND_IMAGE,
    MOMENT_MEDIA_KIND_VIDEO,
    MOMENT_MAX_IMAGES,
)
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

from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

import logging

logger = logging.getLogger(__name__)


# -------------------------------------------------
# Helpers
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

# -------------------------------------------------
# Serializers
# -------------------------------------------------
class MomentSerializer(
    InstanceTargetMixin,
    ImageFileMixin,
    VideoFileMixin,
    ThumbnailFileMixin,
    serializers.ModelSerializer,
):
    owner = serializers.SerializerMethodField(read_only=True)

    # Backward-compatible single image field.
    image = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    # New multi-photo upload field.
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=False,
    )

    video = serializers.FileField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    # Thumbnail is video-only. It may be generated automatically or later replaced.
    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    media_kind = serializers.CharField(read_only=True)
    image_items = serializers.SerializerMethodField(read_only=True)
    cover_image = serializers.SerializerMethodField(read_only=True)
    max_images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Moment
        list_serializer_class = FilterNoneListSerializer
        fields = [
            "id",
            "slug",

            # content
            "caption",
            "image",
            "images",
            "video",
            "thumbnail",

            # media metadata
            "media_kind",
            "image_items",
            "cover_image_id",
            "cover_image",
            "max_images",
            "audio_payload",

            # visibility / UI
            "visibility",
            "is_hidden",

            # interaction counters
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",
            "view_count_internal",

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
            "media_kind",
            "image_items",
            "cover_image",
            "max_images",
            "audio_payload",
            "is_converted",
            "comment_target",
            "reaction_target",
            "owner",
            "comments_count",
            "recomments_count",
            "reactions_count",
            "reactions_breakdown",
        ]

    # -------------------------------------------------
    # Owner DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        Returns OwnerDTO (public or full) or None.
        """
        try:
            request = self.context.get("request")

            # Skip owner during POST response.
            if request and request.method == "POST":
                return None

            owner = build_owner_dto_from_content_object(
                obj,
                context=self.context,
            )

            if not owner:
                return None

            # Hide sensitive fields from visitors.
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

            logger.debug("Moment owner dto=%s", owner)
            return owner

        except Exception:
            logger.exception("get_owner failed for moment id=%s", obj.id)
            return None

    # -------------------------------------------------
    # Media representation
    # -------------------------------------------------
    def get_max_images(self, obj):
        return MOMENT_MAX_IMAGES

    def get_image_items(self, obj):
        """
        Return safe ordered image metadata for clients.

        Full detail pages need cdn_url/image_url so web can render
        every photo in a multi-photo Moment.
        """
        try:
            items = obj.normalized_image_items()
            cover_id = str(obj.cover_image_id or "")

            output = []

            for index, item in enumerate(items):
                item_id = str(item.get("id") or "").strip()
                key = str(item.get("key") or "").strip().lstrip("/")

                if not item_id or not key:
                    continue

                output.append({
                    "id": item_id,
                    "key": key,
                    "order": int(item.get("order", index) or index),
                    "file_name": item.get("file_name") or key.split("/")[-1],
                    "mime_type": item.get("mime_type") or "",
                    "size": int(item.get("size") or 0),
                    "is_cover": item_id == cover_id or bool(item.get("is_cover")),
                    "field_name": f"image_items:{item_id}",

                    # Web display helpers.
                    "cdn_url": _build_asset_cdn_url(key),
                    "image_url": _build_asset_cdn_url(key),
                })

            output.sort(key=lambda value: value.get("order", 0))
            return output

        except Exception:
            logger.exception("get_image_items failed for moment id=%s", obj.id)
            return []

    def get_cover_image(self, obj):
        """
        Return lightweight cover descriptor for grid/feed/detail clients.
        """
        try:
            item = obj.cover_image_item()

            if item and item.get("id"):
                item_id = str(item["id"])
                key = str(item.get("key") or "").strip().lstrip("/")

                return {
                    "id": item_id,
                    "field_name": f"image_items:{item_id}",
                    "source": "image_items",
                    "cdn_url": _build_asset_cdn_url(key),
                    "image_url": _build_asset_cdn_url(key),
                }

            if obj.image:
                return {
                    "id": None,
                    "field_name": "image",
                    "source": "image",
                    "cdn_url": _build_asset_cdn_url(getattr(obj.image, "name", None)),
                    "image_url": _build_asset_cdn_url(getattr(obj.image, "name", None)),
                }

            return None

        except Exception:
            logger.exception("get_cover_image failed for moment id=%s", obj.id)
            return None

    # -------------------------------------------------
    # Ownership helpers
    # -------------------------------------------------
    def _get_request_owner(self):
        """Resolve active owner profile from request."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        return resolve_owner_from_request(request)

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
    # Upload helpers
    # -------------------------------------------------
    def _get_uploaded_images(self):
        """
        Read multi-photo uploads from multipart data.
        Supports both images and images[].
        """
        request = self.context.get("request")
        files = getattr(request, "FILES", None)

        if files and hasattr(files, "getlist"):
            uploaded = files.getlist("images")
            if uploaded:
                return uploaded

            uploaded = files.getlist("images[]")
            if uploaded:
                return uploaded

        raw = self.initial_data.get("images") if hasattr(self, "initial_data") else None

        if not raw:
            return []

        if isinstance(raw, list):
            return raw

        return [raw]

    def _validate_uploaded_images(self, images):
        """
        Validate uploaded photo files.
        """
        if not images:
            return

        if len(images) > MOMENT_MAX_IMAGES:
            raise serializers.ValidationError({
                "images": f"Photo Moment can contain up to {MOMENT_MAX_IMAGES} images."
            })

        for image in images:
            validate_no_executable_file(image)
            validate_image_file(image)
            validate_image_size(image)

    def _save_extra_image(self, instance: Moment, uploaded_file):
        """
        Save an extra image file using Moment's upload path.
        """
        path = Moment.IMAGE.dir_upload(instance, uploaded_file.name)
        return default_storage.save(path, uploaded_file)

    def _build_image_items_from_uploads(
        self,
        *,
        instance: Moment,
        images,
    ):
        """
        Build JSON metadata for first image + extra images.
        """
        items = []

        # First image is saved by the ImageField itself.
        if instance.image and getattr(instance.image, "name", None):
            first = images[0] if images else None

            items.append(
                instance.build_image_item(
                    key=instance.image.name,
                    file_name=getattr(first, "name", None) or instance.image.name.split("/")[-1],
                    mime_type=getattr(first, "content_type", "") or "",
                    size=getattr(first, "size", 0) or 0,
                    order=0,
                    is_cover=True,
                )
            )

        # Remaining images are stored manually and tracked in JSON.
        for index, uploaded in enumerate(images[1:], start=1):
            key = self._save_extra_image(instance, uploaded)

            items.append(
                instance.build_image_item(
                    key=key,
                    file_name=getattr(uploaded, "name", "") or "",
                    mime_type=getattr(uploaded, "content_type", "") or "",
                    size=getattr(uploaded, "size", 0) or 0,
                    order=index,
                    is_cover=False,
                )
            )

        return items

    def _sync_cover_image_flags(
        self,
        *,
        instance: Moment,
        cover_image_id: str | None,
    ) -> list[dict]:
        """
        Keep JSON image_items cover flags in sync with cover_image_id.
        """
        items = instance.normalized_image_items()
        if not items:
            return []

        selected_id = str(cover_image_id or "").strip()

        if not selected_id:
            selected_id = str(items[0].get("id") or "").strip()

        synced_items = []

        for index, item in enumerate(items):
            cloned = dict(item)
            item_id = str(cloned.get("id") or "").strip()

            cloned["order"] = int(cloned.get("order", index) or index)
            cloned["is_cover"] = bool(item_id and item_id == selected_id)

            synced_items.append(cloned)

        return synced_items
    
    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    def create(self, validated_data):
        """
        Owner is resolved by ViewSet.
        Supports:
        - legacy image upload
        - new images[] multi-photo upload
        - single video upload
        """
        validated_data.setdefault(
            "visibility",
            VISIBILITY_GLOBAL,
        )

        # images is a serializer-only field, not a Moment model field.
        validated_data.pop("images", None)

        uploaded_images = self._get_uploaded_images()
        self._validate_uploaded_images(uploaded_images)

        if uploaded_images:
            # Store first image through the legacy ImageField for compatibility.
            validated_data["image"] = uploaded_images[0]
            validated_data["media_kind"] = MOMENT_MEDIA_KIND_IMAGE
            validated_data.pop("video", None)
            validated_data.pop("thumbnail", None)

        elif validated_data.get("image"):
            validated_data["media_kind"] = MOMENT_MEDIA_KIND_IMAGE

        elif validated_data.get("video"):
            validated_data["media_kind"] = MOMENT_MEDIA_KIND_VIDEO
            validated_data.pop("image", None)
            validated_data["image_items"] = []
            validated_data["cover_image_id"] = None

        with transaction.atomic():
            instance = super().create(validated_data)

            if uploaded_images:
                image_items = self._build_image_items_from_uploads(
                    instance=instance,
                    images=uploaded_images,
                )

                cover_id = image_items[0]["id"] if image_items else None

                Moment.objects.filter(pk=instance.pk).update(
                    image_items=image_items,
                    cover_image_id=cover_id,
                    media_kind=MOMENT_MEDIA_KIND_IMAGE,
                    is_converted=True,
                )

                instance.image_items = image_items
                instance.cover_image_id = cover_id
                instance.media_kind = MOMENT_MEDIA_KIND_IMAGE
                instance.is_converted = True

        return instance

    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def update(self, instance, validated_data):
        self._assert_owner(instance)

        if "images" in validated_data:
            raise serializers.ValidationError({
                "images": "Moment photos cannot be changed after posting."
            })

        forbidden_fields = {
            "is_active",
            "is_suspended",
            "reports_count",
            "content_type",
            "object_id",
            "media_kind",
            "image_items",
            "audio_payload",
        }

        for field in forbidden_fields:
            if field in validated_data:
                raise serializers.ValidationError(
                    f"Field '{field}' cannot be modified."
                )

        # Photo/video files cannot be replaced after upload.
        if "image" in validated_data:
            raise serializers.ValidationError({
                "image": "Moment photos cannot be changed after posting."
            })

        if "video" in validated_data:
            raise serializers.ValidationError({
                "video": "Moment video cannot be changed after posting."
            })

        # Thumbnail replacement is allowed only for video Moments.
        if "thumbnail" in validated_data:
            if not instance.video:
                raise serializers.ValidationError({
                    "thumbnail": "Thumbnail can only be changed for video Moments."
                })

        # Cover pin is allowed only for photo Moments.
        if "cover_image_id" in validated_data:
            if instance.video:
                raise serializers.ValidationError({
                    "cover_image_id": "Video Moments use thumbnail, not cover image."
                })

            cover_image_id = validated_data.get("cover_image_id")
            synced_items = self._sync_cover_image_flags(
                instance=instance,
                cover_image_id=cover_image_id,
            )

            if synced_items:
                validated_data["image_items"] = synced_items

        return super().update(instance, validated_data)

    # -------------------------------------------------
    # Cross-field validation
    # -------------------------------------------------
    def validate(self, attrs):
        request = self.context.get("request")

        # Enforce only on write.
        if request and request.method in ("POST", "PUT", "PATCH"):
            # Block ownership injection.
            forbidden = {"content_type", "object_id"}
            for key in forbidden:
                if key in self.initial_data:
                    raise serializers.ValidationError({
                        key: "This field is not allowed."
                    })

            uploaded_images = self._get_uploaded_images()
            legacy_image = attrs.get("image")
            video = attrs.get("video")
            thumbnail = attrs.get("thumbnail")

            if self.instance is not None:
                existing_image = getattr(self.instance, "image", None)
                existing_video = getattr(self.instance, "video", None)
                existing_items = self.instance.normalized_image_items()
            else:
                existing_image = None
                existing_video = None
                existing_items = []

            has_new_photo = bool(uploaded_images) or bool(legacy_image)
            has_existing_photo = bool(existing_image) or bool(existing_items)
            has_photo = has_new_photo or has_existing_photo
            has_video = bool(video) or bool(existing_video)

            if uploaded_images and legacy_image:
                raise serializers.ValidationError({
                    "images": "Use either 'images' or legacy 'image', not both."
                })

            if uploaded_images:
                self._validate_uploaded_images(uploaded_images)

            if has_new_photo and has_video:
                raise serializers.ValidationError(
                    "Moment cannot contain both images and video."
                )

            if video and has_photo:
                raise serializers.ValidationError(
                    "Moment cannot contain both images and video."
                )

            if request.method == "POST" and not has_new_photo and not video:
                raise serializers.ValidationError(
                    "Moment must contain either images or a video."
                )

            if thumbnail and not (video or existing_video):
                raise serializers.ValidationError({
                    "thumbnail": "Thumbnail can only be used with video Moments."
                })

            cover_image_id = attrs.get("cover_image_id")
            if cover_image_id:
                if self.instance is None:
                    raise serializers.ValidationError({
                        "cover_image_id": "Cover image can only be changed after creation."
                    })

                valid_ids = {
                    str(item.get("id"))
                    for item in self.instance.normalized_image_items()
                    if item.get("id")
                }

                if str(cover_image_id) not in valid_ids:
                    raise serializers.ValidationError({
                        "cover_image_id": "Invalid cover image."
                    })

        return attrs

    # -------------------------------------------------
    # Representation hardening
    # -------------------------------------------------
    def to_representation(self, obj):
        request = self.context.get("request")
        viewer = request.user if request and request.user.is_authenticated else None

        # Hard media visibility gate.
        if obj.video and not obj.is_converted:
            owner = resolve_owner_from_request(request) if request else None

            # Visitor or non-owner cannot see in-progress media.
            if not owner or (
                obj.content_type_id
                != ContentType.objects.get_for_model(owner.__class__).id
                or obj.object_id != owner.id
            ):
                return None

        data = super().to_representation(obj)

        # Owner-safe conversion payload.
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

        # Visitor hardening.
        if not viewer:
            data.pop("visibility", None)
            data.pop("is_hidden", None)
            data.pop("reactions_breakdown", None)

        return data


# -------------------------------------------------
# Lightweight serializer for profile grid
# -------------------------------------------------
class MomentProfileGridSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for profile Moment grid.

    Used by /posts/moments/me/.
    Keeps the payload small but includes enough data for:
    - legacy image/video Moments
    - multi-photo Moments
    - cover image preview
    - owner action menu detection
    """

    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
        use_url=True,
    )

    image_items = serializers.SerializerMethodField(read_only=True)
    cover_image = serializers.SerializerMethodField(read_only=True)
    max_images = serializers.SerializerMethodField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Moment
        fields = [
            "id",
            "slug",

            # Content
            "caption",

            # Legacy media fields
            "image",
            "video",
            "thumbnail",

            # Multi-photo metadata
            "media_kind",
            "image_items",
            "cover_image_id",
            "cover_image",
            "max_images",

            # Visibility / UI
            "visibility",
            "is_hidden",

            # Pipeline / timestamps
            "is_converted",
            "published_at",
            "updated_at",

            # Owner action menu support
            "owner",
        ]
        read_only_fields = fields

    # -------------------------------------------------
    # Multi-photo helpers
    # -------------------------------------------------
    def get_image_items(self, obj):
        """
        Return ordered image items with CDN URLs for web grid previews.

        Important:
        - field_name is used by asset-delivery warmup.
        - cdn_url is used as the actual <img src>.
        """
        try:
            if hasattr(obj, "normalized_image_items"):
                items = obj.normalized_image_items()
            else:
                items = getattr(obj, "image_items", None) or []

            if not isinstance(items, list):
                return []

            cover_id = str(getattr(obj, "cover_image_id", "") or "")
            payload = []

            cleaned = [
                item for item in items
                if isinstance(item, dict) and item.get("id") and item.get("key")
            ]

            cleaned = sorted(
                cleaned,
                key=lambda item: int(item.get("order", 0) or 0),
            )

            for index, item in enumerate(cleaned):
                item_id = str(item.get("id") or "").strip()
                key = str(item.get("key") or "").strip().lstrip("/")

                if not item_id or not key:
                    continue

                payload.append({
                    "id": item_id,
                    "key": key,
                    "order": int(item.get("order", index) or index),
                    "file_name": item.get("file_name") or key.split("/")[-1],
                    "mime_type": item.get("mime_type") or "",
                    "size": int(item.get("size") or 0),
                    "is_cover": item_id == cover_id or bool(item.get("is_cover")),
                    "field_name": f"image_items:{item_id}",

                    # Web display source.
                    "cdn_url": _build_asset_cdn_url(key),
                    "image_url": _build_asset_cdn_url(key),
                })

            return payload

        except Exception:
            logger.exception("get_image_items failed for moment id=%s", obj.id)
            return []

    def get_cover_image(self, obj):
        """
        Return lightweight cover descriptor.
        """
        try:
            item = obj.cover_image_item()

            if item:
                item_id = str(item.get("id") or "")
                key = str(item.get("key") or "").strip().lstrip("/")

                if item_id:
                    return {
                        "id": item_id,
                        "field_name": f"image_items:{item_id}",
                        "source": "image_items",
                        "cdn_url": _build_asset_cdn_url(key),
                        "image_url": _build_asset_cdn_url(key),
                    }

            if getattr(obj, "image", None):
                return {
                    "id": None,
                    "field_name": "image",
                    "source": "image",
                }

            return None

        except Exception:
            logger.exception("get_cover_image failed for moment id=%s", obj.id)
            return None

    def get_max_images(self, obj):
        """
        Return current backend limit for client display.
        """
        try:
            from apps.posts.constants.moments import MOMENT_MAX_IMAGES
            return MOMENT_MAX_IMAGES
        except Exception:
            return None

    # -------------------------------------------------
    # Owner DTO
    # -------------------------------------------------
    def get_owner(self, obj):
        """
        Minimal owner payload.

        For /me/ this is current owner's content, but we still verify
        against request owner to avoid blindly marking unrelated payloads.
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
            logger.exception("get_owner failed for profile grid moment id=%s", obj.id)
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

        # Owner-safe conversion payload.
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
