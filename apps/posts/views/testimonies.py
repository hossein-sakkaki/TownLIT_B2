# apps/posts/views/testimonies.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-01-01.
# Last Update by Hossein Sakkaki on 2026-11-02.

import logging
import os

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.ownership.owner_gate_mixins import OwnerGateMixin
from apps.core.ownership.utils import resolve_owner_from_request
from apps.core.pagination import ConfigurablePagination, FeedCursorPagination
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.visibility.query import VisibilityQuery
from apps.media_conversion.services.image_variants import build_image_variants
from apps.media_conversion.services.media_manifest import (
    build_asset_payload,
    update_instance_media_asset,
)
from apps.media_conversion.services.media_metadata import image_metadata_from_storage
from apps.media_conversion.services.query import exclude_unready_media
from apps.posts.models.testimony import Testimony
from apps.posts.serializers.testimonies import (
    TestimonyProfileHeaderSerializer,
    TestimonySerializer,
)
from apps.posts.services.testimony_content_safety import (
    enforce_testimony_content_safety,
)
from apps.posts.services.testimony_media_content_safety import (
    enforce_testimony_image_asset_safety,
    enforce_testimony_media_content_safety,
)
from apps.profiles.models.member import Member
from utils.common.image_utils import convert_image_to_jpg
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file
from apps.content_safety.view_mixins import (
    ContentSafetyJobResponseMixin,
)

logger = logging.getLogger(__name__)


class TestimonyViewSet(
    ContentSafetyJobResponseMixin,
    OwnerGateMixin,
    viewsets.ModelViewSet,
):
    """Testimony API: visibility-aware, interaction-ready, cursor feeds."""

    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    pagination_class = ConfigurablePagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        """Allow public access only for safe read actions."""
        if self.action in ["retrieve", "explore"]:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        base = (
            Testimony.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )
        if self.action in {
            "retrieve",
            "update",
            "partial_update",
            "destroy",
            "thumbnail",
            "audio_artwork",
        }:
            if self.request.user and self.request.user.is_authenticated:
                return base
            return exclude_unready_media(base)
        if self.action == "explore" and not self.request.user.is_authenticated:
            return exclude_unready_media(base.filter(visibility="global"))
        qs = VisibilityQuery.for_viewer(viewer=self.request.user, base_queryset=base)
        return exclude_unready_media(qs)

    def _get_owner(self):
        """Testimony belongs to Member, not the active generic owner."""
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None
        return getattr(user, "member_profile", None)

    def _assert_is_owner(self, obj):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner context.")
        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        if obj.content_type_id != owner_ct.id or obj.object_id != owner.id:
            raise PermissionDenied("You do not own this Testimony.")

    def _rewind_uploaded_file(self, uploaded):
        try:
            uploaded.seek(0)
        except Exception:
            pass

    def _validate_uploaded_image(self, uploaded):
        """Validate file and rewind between validators."""
        validate_no_executable_file(uploaded)
        self._rewind_uploaded_file(uploaded)
        validate_image_file(uploaded)
        self._rewind_uploaded_file(uploaded)
        validate_image_size(uploaded)
        self._rewind_uploaded_file(uploaded)

    def _safe_delete_storage_key(self, key: str | None, *, label: str = "source"):
        """Best-effort cleanup of an exact key; do not delete variants."""
        try:
            if not key:
                return
            clean_key = str(key).strip().lstrip("/")
            if clean_key and default_storage.exists(clean_key):
                default_storage.delete(clean_key)
                logger.info("Deleted %s file: %s", label, clean_key)
        except Exception:
            logger.warning(
                "Could not delete %s file: %s", label, key, exc_info=True
            )

    def _build_and_store_image_asset(
        self, *, instance, field_name: str, key: str
    ):
        """Build metadata/variants for owner-managed image assets."""
        clean_key = str(key or "").strip().lstrip("/")
        if not clean_key:
            return
        image_meta = image_metadata_from_storage(clean_key)
        variant_dir = os.path.dirname(clean_key)
        basename = os.path.splitext(os.path.basename(clean_key))[0]
        variants = build_image_variants(
            source_key=clean_key,
            base_output_dir=f"{variant_dir}/variants",
            basename=basename,
        )
        payload = build_asset_payload(
            key=clean_key,
            metadata=image_meta,
            variants=variants,
            extra={"mime_type": "image/jpeg"},
        )
        update_instance_media_asset(
            instance=instance, field_name=field_name, payload=payload
        )

    def perform_create(self, serializer):
        """Persist testimony, then schedule configured content safety jobs."""
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")
        ttype = serializer.validated_data.get("type")
        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        exists = Testimony.objects.filter(
            content_type=owner_ct, object_id=owner.id, type=ttype
        ).exists()
        if exists:
            raise PermissionDenied(f"You already have a '{ttype}' testimony.")
        enforce_testimony_content_safety(
            validated_data=serializer.validated_data, actor=self.request.user
        )
        enforce_testimony_media_content_safety(
            validated_data=serializer.validated_data, actor=self.request.user
        )
        with transaction.atomic():
            exists = Testimony.objects.filter(
                content_type=owner_ct, object_id=owner.id, type=ttype
            ).exists()
            if exists:
                raise PermissionDenied(f"You already have a '{ttype}' testimony.")
            instance = serializer.save(content_type=owner_ct, object_id=owner.id)
            self.schedule_content_safety_jobs(
                instance=instance, submitted_data=serializer.validated_data
            )

    def perform_update(self, serializer):
        """Owner-safe update routed through existing content safety."""
        obj = self.get_object()
        self._assert_is_owner(obj)
        enforce_testimony_content_safety(
            validated_data=serializer.validated_data,
            actor=self.request.user,
            instance=obj,
        )
        enforce_testimony_media_content_safety(
            validated_data=serializer.validated_data,
            actor=self.request.user,
            instance=obj,
        )
        with transaction.atomic():
            instance = serializer.save(updated_at=timezone.now())
            self.schedule_content_safety_jobs(
                instance=instance, submitted_data=serializer.validated_data
            )

    def perform_destroy(self, instance):
        self._assert_is_owner(instance)
        instance.delete()

    @action(
        detail=True,
        methods=["patch"],
        url_path="thumbnail",
        parser_classes=[MultiPartParser, FormParser],
    )
    def thumbnail(self, request, slug=None):
        """Publish a ready video poster without reconverting the video."""
        from apps.posts.services.testimony_thumbnail_update import (
            ThumbnailUpdateConflict,
            ThumbnailUpdateError,
            update_testimony_thumbnail,
        )

        obj = self.get_object()
        self._assert_is_owner(obj)
        if obj.type != Testimony.TYPE_VIDEO:
            return Response(
                {"detail": "Thumbnail can only be updated for video testimonies."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        uploaded = request.FILES.get("thumbnail")
        if not uploaded:
            return Response(
                {"thumbnail": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            self._validate_uploaded_image(uploaded)
        except Exception:
            logger.warning(
                "Invalid testimony thumbnail upload: id=%s",
                obj.pk,
                exc_info=True,
            )
            return Response(
                {"thumbnail": "Invalid image file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._rewind_uploaded_file(uploaded)
        enforce_testimony_image_asset_safety(
            file_obj=uploaded,
            actor=request.user,
            field_name="thumbnail",
        )
        self._rewind_uploaded_file(uploaded)
        try:
            refreshed = update_testimony_thumbnail(obj=obj, uploaded=uploaded)
        except ThumbnailUpdateConflict:
            return Response(
                {"thumbnail": "Thumbnail changed concurrently. Please retry."},
                status=status.HTTP_409_CONFLICT,
            )
        except ThumbnailUpdateError:
            logger.exception("Thumbnail publication failed: id=%s", obj.pk)
            return Response(
                {"thumbnail": "Could not prepare thumbnail."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            self.get_serializer(refreshed).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="audio-artwork",
        parser_classes=[MultiPartParser, FormParser],
    )
    def audio_artwork(self, request, slug=None):
        """
        Owner-only endpoint to update optional artwork for audio testimony.

        Audio artwork is normalized synchronously and directly rebound in DB
        to prevent MediaAutoConvertMixin from reconverting primary audio.
        """
        obj = self.get_object()
        self._assert_is_owner(obj)
        if obj.type != Testimony.TYPE_AUDIO:
            return Response(
                {"detail": "Audio artwork can only be updated for audio testimonies."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        uploaded = request.FILES.get("audio_artwork")
        if not uploaded:
            return Response(
                {"audio_artwork": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            self._validate_uploaded_image(uploaded)
        except Exception as exc:
            logger.warning(
                "Invalid testimony audio artwork upload for testimony id=%s: %s",
                getattr(obj, "id", None),
                exc,
                exc_info=True,
            )
            return Response(
                {"audio_artwork": "Invalid image file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._rewind_uploaded_file(uploaded)
        enforce_testimony_image_asset_safety(
            file_obj=uploaded,
            actor=request.user,
            field_name="audio_artwork",
        )
        self._rewind_uploaded_file(uploaded)
        old_artwork_key = getattr(getattr(obj, "audio_artwork", None), "name", None)
        raw_artwork_key = None
        converted_key = None
        try:
            self._rewind_uploaded_file(uploaded)
            field = Testimony._meta.get_field("audio_artwork")
            generated_raw_key = field.generate_filename(obj, uploaded.name)
            raw_artwork_key = default_storage.save(
                str(generated_raw_key).lstrip("/"), uploaded
            )
            raw_artwork_key = str(raw_artwork_key or "").strip().lstrip("/")
            if not raw_artwork_key:
                return Response(
                    {"audio_artwork": "Artwork was not saved."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            logger.info(
                "Audio artwork raw upload saved: testimony=%s key=%s",
                getattr(obj, "id", None),
                raw_artwork_key,
            )
            converted_key = convert_image_to_jpg(
                source_path=raw_artwork_key,
                instance=obj,
                fileupload=Testimony.AUDIO_ARTWORK,
            )
            converted_key = str(converted_key or "").strip().lstrip("/")
            if not converted_key:
                return Response(
                    {"audio_artwork": "Could not prepare artwork."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updated_count = Testimony.objects.filter(pk=obj.pk).update(
                audio_artwork=converted_key,
                updated_at=timezone.now(),
            )
            if updated_count != 1:
                return Response(
                    {"audio_artwork": "Could not save artwork."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            refreshed = Testimony.objects.get(pk=obj.pk)
            persisted_key = getattr(
                getattr(refreshed, "audio_artwork", None), "name", None
            )
            persisted_key = str(persisted_key or "").strip().lstrip("/")
            if persisted_key != converted_key:
                logger.error(
                    "Audio artwork DB bind mismatch: testimony=%s expected=%s actual=%s",
                    getattr(obj, "id", None),
                    converted_key,
                    persisted_key,
                )
                return Response(
                    {"audio_artwork": "Artwork was prepared but not attached."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            self._build_and_store_image_asset(
                instance=refreshed,
                field_name="audio_artwork",
                key=converted_key,
            )
            refreshed = Testimony.objects.get(pk=obj.pk)
            logger.info(
                "Audio artwork updated: testimony=%s old=%s raw=%s converted=%s",
                getattr(obj, "id", None),
                old_artwork_key,
                raw_artwork_key,
                converted_key,
            )
            if raw_artwork_key and raw_artwork_key != converted_key:
                self._safe_delete_storage_key(
                    raw_artwork_key, label="raw testimony audio artwork"
                )
            if old_artwork_key and old_artwork_key != converted_key:
                self._safe_delete_storage_key(
                    old_artwork_key, label="old testimony audio artwork"
                )
        except Exception as exc:
            logger.exception(
                "Failed to normalize testimony audio artwork for testimony id=%s: %s",
                getattr(obj, "id", None),
                exc,
            )
            if raw_artwork_key and raw_artwork_key != converted_key:
                self._safe_delete_storage_key(
                    raw_artwork_key, label="failed raw testimony audio artwork"
                )
            return Response(
                {"audio_artwork": "Could not prepare artwork."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response_serializer = self.get_serializer(refreshed)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
    )
    def feed(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def me(self, request):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied(
                "Testimonies are available for member profiles only."
            )
        owner_ct = ContentType.objects.get_for_model(
            Member, for_concrete_model=False
        )
        qs = (
            Testimony.objects.filter(
                content_type_id=owner_ct.id,
                object_id=owner.id,
            )
            .filter(Q(is_active=True) | Q(is_converted=False))
            .only(
                "id", "slug", "type", "title", "content",
                "audio", "video", "thumbnail", "audio_artwork", "media_assets",
                "visibility", "is_hidden", "published_at", "updated_at",
                "is_converted", "content_type_id", "object_id",
            )
            .order_by("-published_at", "-id")
        )
        try:
            page = self.paginate_queryset(qs)
        except NotFound:
            return Response(
                {"count": qs.count(), "next": None, "previous": None, "results": []}
            )
        serializer = TestimonyProfileHeaderSerializer(
            page,
            many=True,
            context={"request": request},
        )
        results = [item for item in serializer.data if item is not None]
        return self.get_paginated_response(results)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def explore(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Return one owner testimony of each type; web compatible shape."""
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied(
                "Testimonies are available for member profiles only."
            )
        owner_ct = ContentType.objects.get_for_model(
            Member,
            for_concrete_model=False,
        )
        qs = (
            Testimony.objects.filter(
                content_type_id=owner_ct.id,
                object_id=owner.id,
            )
            .filter(Q(is_active=True) | Q(is_converted=False))
            .only(
                "id", "slug", "type", "title", "content",
                "audio", "video", "thumbnail", "audio_artwork", "media_assets",
                "visibility", "is_hidden", "published_at", "updated_at",
                "is_converted", "content_type_id", "object_id",
            )
            .order_by("-published_at", "-id")
        )
        by_type = {}
        for item in qs:
            if item.type not in by_type:
                by_type[item.type] = item

        def empty_payload(ttype):
            return {
                "exists": False,
                "type": ttype,
                "id": None,
                "slug": None,
                "title": None,
                "content": None,
                "audio": None,
                "video": None,
                "thumbnail": None,
                "audio_artwork": None,
                "thumbnail_asset": None,
                "audio_artwork_asset": None,
                "is_converted": False,
                "converting": False,
                "ready_status": None,
                "job_id": None,
                "media_pipeline": None,
                "owner": {
                    "type": "member",
                    "id": owner.id,
                    "is_me": True,
                },
            }

        def pack(ttype):
            item = by_type.get(ttype)
            if not item:
                return empty_payload(ttype)
            data = TestimonyProfileHeaderSerializer(
                item,
                context={"request": request},
            ).data
            if not data:
                return empty_payload(ttype)
            data["exists"] = True
            is_media_testimony = item.type in (
                Testimony.TYPE_VIDEO,
                Testimony.TYPE_AUDIO,
            )
            if "converting" not in data:
                data["converting"] = False
            if "ready_status" not in data:
                data["ready_status"] = (
                    "done" if item.is_converted else None
                )
            if "job_id" not in data:
                data["job_id"] = None
            if item.type == Testimony.TYPE_AUDIO:
                data["audio_key"] = getattr(item.audio, "name", None)
                data["audio_artwork_key"] = getattr(
                    item.audio_artwork, "name", None
                )
            if item.type == Testimony.TYPE_VIDEO:
                data["video_key"] = getattr(item.video, "name", None)
                data["thumbnail_key"] = getattr(
                    item.thumbnail, "name", None
                )
            if item.type == Testimony.TYPE_WRITTEN:
                content = getattr(item, "content", "") or ""
                data["excerpt"] = (
                    content[:140] + "…" if len(content) > 140 else content
                )
            data["owner"] = {
                "type": "member", "id": owner.id, "is_me": True,
            }
            return data

        return Response(
            {
                "audio": pack(Testimony.TYPE_AUDIO),
                "video": pack(Testimony.TYPE_VIDEO),
                "written": pack(Testimony.TYPE_WRITTEN),
            },
            status=status.HTTP_200_OK,
        )

    def _resolve_owner_object(self, obj):
        """Resolve owner from content type and object id."""
        try:
            ct = obj.content_type
            if not ct or not obj.object_id:
                return None
            model_cls = ct.model_class()
            if not model_cls:
                return None
            return model_cls.objects.filter(pk=obj.object_id).first()
        except Exception:
            logger.exception("Failed to resolve testimony owner object")
            return None

    def _resolve_owner_user_and_member(self, obj):
        """Normalize owner as (user, member, raw owner)."""
        owner_obj = self._resolve_owner_object(obj)
        if not owner_obj:
            return None, None, None
        if hasattr(owner_obj, "user"):
            owner_user = getattr(owner_obj, "user", None)
            owner_member = owner_obj
            return owner_user, owner_member, owner_obj
        try:
            from apps.accounts.models.user import CustomUser
            if isinstance(owner_obj, CustomUser):
                owner_user = owner_obj
                owner_member = getattr(owner_user, "member_profile", None)
                return owner_user, owner_member, owner_obj
        except Exception:
            logger.exception("CustomUser import/type check failed")
        return None, None, owner_obj

    def _profile_gate_payload(self, owner_user, reason):
        """Build a stable profile gate response."""
        return {
            "profile_gate": {
                "key": "profile_privacy_redirect",
                "reason": reason,
                "redirect_to": f"/lit/{owner_user.username}",
            }
        }

    def _safe_is_friend(self, viewer, owner_user):
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return False
        fn = getattr(self, "_is_friend", None)
        if callable(fn):
            try:
                return bool(fn(viewer, owner_user))
            except Exception:
                logger.exception("Friendship check failed")
        return False

    def _safe_is_confidant(self, viewer, owner_member):
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return False
        fn = getattr(self, "_is_confidant", None)
        if callable(fn):
            try:
                return bool(fn(viewer, owner_member))
            except Exception:
                logger.exception("Confidant check failed")
        return False

    def _apply_owner_profile_gate_if_needed(self, request, obj):
        """Apply owner account and profile privacy gates."""
        viewer = request.user if request.user.is_authenticated else None
        owner_user, owner_member, owner_obj = (
            self._resolve_owner_user_and_member(obj)
        )
        if not owner_user or not owner_member:
            return None
        if viewer and viewer.is_authenticated and viewer.id == owner_user.id:
            return None
        if getattr(owner_user, "is_deleted", False):
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if getattr(owner_user, "is_suspended", False):
            return Response(
                self._profile_gate_payload(owner_user, reason="account_suspended"),
                status=status.HTTP_200_OK,
            )
        if getattr(owner_user, "is_account_paused", False):
            return Response(
                self._profile_gate_payload(owner_user, reason="account_paused"),
                status=status.HTTP_200_OK,
            )
        if getattr(owner_member, "is_hidden_by_confidants", False):
            if self._safe_is_confidant(viewer, owner_member):
                return None
            return Response(
                self._profile_gate_payload(owner_user, reason="hidden_by_confidants"),
                status=status.HTTP_200_OK,
            )
        if getattr(owner_member, "is_privacy", False):
            if self._safe_is_friend(viewer, owner_user):
                return None
            return Response(
                self._profile_gate_payload(owner_user, reason="private_profile"),
                status=status.HTTP_200_OK,
            )
        return None

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        self.apply_hard_owner_gate(request, obj)
        redirect_response = self.apply_profile_privacy_gate(request, obj)
        if redirect_response:
            return redirect_response
        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=obj)
        if reason is not None:
            return Response(
                {
                    "detail": "Access restricted.",
                    "code": reason,
                    "content_type": "testimony",
                    "slug": obj.slug,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            Testimony.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("testimony analytics update failed")
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
