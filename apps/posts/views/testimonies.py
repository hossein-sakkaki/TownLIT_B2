# apps/posts/views/testimonies.py

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
from apps.profiles.models.member import Member
from utils.common.image_utils import convert_image_to_jpg
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

logger = logging.getLogger(__name__)


class TestimonyViewSet(OwnerGateMixin, viewsets.ModelViewSet):
    """
    Testimony API (post-like)

    - Visibility-aware
    - Interaction-ready
    - Cursor feed support
    - Owner-safe
    """

    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    pagination_class = ConfigurablePagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # -------------------------------------------------
    # Permissions (Visitor-safe)
    # -------------------------------------------------
    def get_permissions(self):
        """
        Allow public access ONLY for safe read actions.
        """
        if self.action in [
            "retrieve",
            "explore",
        ]:
            return [AllowAny()]

        return super().get_permissions()

    # -------------------------------------------------
    # Base queryset (ordering only)
    # -------------------------------------------------
    def get_queryset(self):
        base = (
            Testimony.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # retrieve: allow authenticated users to reach the object.
        # Owner conversion UX is handled later by serializer gate.
        if self.action == "retrieve":
            if self.request.user and self.request.user.is_authenticated:
                return base

            return exclude_unready_media(base)

        # explore for anonymous: global only, and hide unconverted.
        if self.action == "explore" and not self.request.user.is_authenticated:
            return exclude_unready_media(base.filter(visibility="global"))

        # default list/feed: visibility-aware, and hide unconverted.
        qs = VisibilityQuery.for_viewer(
            viewer=self.request.user,
            base_queryset=base,
        )
        return exclude_unready_media(qs)

    # -------------------------------------------------
    # Owner resolver
    # -------------------------------------------------
    def _get_owner(self):
        """
        Testimony is Member-only.

        Do not use the generic active-owner resolver here, because Testimony
        is attached directly to Member through GenericRelation.
        """
        user = getattr(self.request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            return None

        return getattr(user, "member_profile", None)

    def _assert_is_owner(self, obj):
        owner = self._get_owner()

        if not owner:
            raise PermissionDenied("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        if (
            obj.content_type_id != owner_ct.id
            or obj.object_id != owner.id
        ):
            raise PermissionDenied("You do not own this Testimony.")

    # -------------------------------------------------
    # Upload / image helpers
    # -------------------------------------------------
    def _rewind_uploaded_file(self, uploaded):
        try:
            uploaded.seek(0)
        except Exception:
            pass

    def _validate_uploaded_image(self, uploaded):
        """
        Run the same image/security validators before saving the upload.
        Rewind between validators because validators may read file content.
        """
        validate_no_executable_file(uploaded)
        self._rewind_uploaded_file(uploaded)

        validate_image_file(uploaded)
        self._rewind_uploaded_file(uploaded)

        validate_image_size(uploaded)
        self._rewind_uploaded_file(uploaded)

    def _safe_delete_storage_key(
        self,
        key: str | None,
        *,
        label: str = "source",
    ):
        """
        Best-effort storage cleanup.

        Only deletes exact stored keys. Variants are intentionally left alone
        unless a future cleanup utility removes whole variant directories.
        """
        try:
            if not key:
                return

            clean_key = str(key).strip().lstrip("/")

            if clean_key and default_storage.exists(clean_key):
                default_storage.delete(clean_key)

                logger.info(
                    "Deleted %s file: %s",
                    label,
                    clean_key,
                )

        except Exception:
            logger.warning(
                "Could not delete %s file: %s",
                label,
                key,
                exc_info=True,
            )

    def _build_and_store_image_asset(
        self,
        *,
        instance,
        field_name: str,
        key: str,
    ):
        """
        Build image metadata and variants immediately.

        This is used for owner-managed profile/banner images where the UI
        needs a fresh response right away, while still keeping storage
        normalized and consistent with the rest of the media system.
        """
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
            extra={
                "mime_type": "image/jpeg",
            },
        )

        update_instance_media_asset(
            instance=instance,
            field_name=field_name,
            payload=payload,
        )

    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    @transaction.atomic
    def perform_create(self, serializer):
        owner = self._get_owner()

        if not owner:
            raise PermissionDenied("Invalid owner type.")

        ttype = serializer.validated_data.get("type")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        # Enforce: one testimony per type per owner.
        exists = Testimony.objects.filter(
            content_type=owner_ct,
            object_id=owner.id,
            type=ttype,
        ).exists()

        if exists:
            raise PermissionDenied(
                f"You already have a '{ttype}' testimony."
            )

        serializer.save(
            content_type=owner_ct,
            object_id=owner.id,
        )

    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def perform_update(self, serializer):
        obj = self.get_object()
        self._assert_is_owner(obj)
        serializer.save(updated_at=timezone.now())

    # -------------------------------------------------
    # Delete
    # -------------------------------------------------
    def perform_destroy(self, instance):
        self._assert_is_owner(instance)
        instance.delete()

    # -------------------------------------------------
    # Video thumbnail / profile banner update
    # -------------------------------------------------
    @action(
        detail=True,
        methods=["patch"],
        url_path="thumbnail",
        parser_classes=[MultiPartParser, FormParser],
    )
    def thumbnail(self, request, slug=None):
        """
        Owner-only endpoint to update the profile/banner thumbnail for
        a video testimony.

        This does not replace or reconvert the video.

        The uploaded image still goes through the image normalization path:
        raw upload -> convert_image_to_jpg -> bind final JPG -> build variants.

        It bypasses the generic async MediaAutoConvert/Celery flow so the
        profile banner can update immediately and not get stuck in conversion.
        """
        obj = self.get_object()
        self._assert_is_owner(obj)

        if obj.type != Testimony.TYPE_VIDEO:
            return Response(
                {
                    "detail": "Thumbnail can only be updated for video testimonies."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded = request.FILES.get("thumbnail")

        if not uploaded:
            return Response(
                {
                    "thumbnail": "This field is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            self._validate_uploaded_image(uploaded)
        except Exception as exc:
            logger.warning(
                "Invalid testimony thumbnail upload for testimony id=%s: %s",
                getattr(obj, "id", None),
                exc,
                exc_info=True,
            )

            return Response(
                {
                    "thumbnail": "Invalid image file."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_thumbnail_key = getattr(
            getattr(obj, "thumbnail", None),
            "name",
            None,
        )

        self._rewind_uploaded_file(uploaded)

        try:
            # Step 1:
            # Save raw upload while bypassing the generic async converter.
            obj._skip_media_autoconvert_once = True
            obj.thumbnail = uploaded
            obj.updated_at = timezone.now()
            obj.save(
                update_fields=[
                    "thumbnail",
                    "updated_at",
                ]
            )

            refreshed = self.get_object()

            raw_thumbnail_key = getattr(
                getattr(refreshed, "thumbnail", None),
                "name",
                None,
            )

            if not raw_thumbnail_key:
                return Response(
                    {
                        "thumbnail": "Thumbnail was not saved."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step 2:
            # Normalize synchronously through the same converter utility used
            # by the project image pipeline.
            converted_key = convert_image_to_jpg(
                source_path=raw_thumbnail_key,
                instance=refreshed,
                fileupload=Testimony.THUMBNAIL,
            )

            converted_key = str(converted_key or "").strip().lstrip("/")

            if not converted_key:
                return Response(
                    {
                        "thumbnail": "Could not prepare thumbnail."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step 3:
            # Bind the normalized JPG while again bypassing async autoconvert.
            refreshed._skip_media_autoconvert_once = True
            refreshed.thumbnail.name = converted_key
            refreshed.updated_at = timezone.now()
            refreshed.save(
                update_fields=[
                    "thumbnail",
                    "updated_at",
                ]
            )

            refreshed = self.get_object()

            # Step 4:
            # Build metadata and variants immediately so profile/summary
            # responses can render the new banner without waiting for Celery.
            self._build_and_store_image_asset(
                instance=refreshed,
                field_name="thumbnail",
                key=converted_key,
            )

            # Step 5:
            # Best-effort cleanup of temporary/raw and old main thumbnail.
            if raw_thumbnail_key != converted_key:
                self._safe_delete_storage_key(
                    raw_thumbnail_key,
                    label="raw testimony thumbnail",
                )

            if old_thumbnail_key and old_thumbnail_key != converted_key:
                self._safe_delete_storage_key(
                    old_thumbnail_key,
                    label="old testimony thumbnail",
                )

        except Exception as exc:
            logger.exception(
                "Failed to normalize testimony thumbnail for testimony id=%s: %s",
                getattr(obj, "id", None),
                exc,
            )

            return Response(
                {
                    "thumbnail": "Could not prepare thumbnail."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        refreshed = self.get_object()
        response_serializer = self.get_serializer(refreshed)

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    # -------------------------------------------------
    # Audio artwork update
    # -------------------------------------------------
    @action(
        detail=True,
        methods=["patch"],
        url_path="audio-artwork",
        parser_classes=[MultiPartParser, FormParser],
    )
    def audio_artwork(self, request, slug=None):
        """
        Owner-only endpoint to update optional artwork for audio testimony.

        This does not replace the audio file.
        It only updates `audio_artwork`.

        Audio artwork intentionally keeps using the generic serializer/model
        save path for now, matching the existing media conversion behavior.
        """
        obj = self.get_object()
        self._assert_is_owner(obj)

        if obj.type != Testimony.TYPE_AUDIO:
            return Response(
                {
                    "detail": "Audio artwork can only be updated for audio testimonies."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded = request.FILES.get("audio_artwork")

        if not uploaded:
            return Response(
                {
                    "audio_artwork": "This field is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(
            obj,
            data={
                "audio_artwork": uploaded,
            },
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save(updated_at=timezone.now())

        refreshed = self.get_object()
        response_serializer = self.get_serializer(refreshed)

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    # -------------------------------------------------
    # Feed (cursor-based, home timeline)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # My testimonies - lightweight profile header
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def me(self, request):
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
            Testimony.objects
            .filter(
                content_type_id=owner_ct.id,
                object_id=owner.id,
                is_active=True,
            )
            .only(
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
                "audio_artwork",
                "media_assets",

                # Visibility / UI.
                "visibility",
                "is_hidden",

                # Timestamps / pipeline.
                "published_at",
                "updated_at",
                "is_converted",

                # Ownership for owner action detection.
                "content_type_id",
                "object_id",
            )
            .order_by("-published_at", "-id")
        )

        try:
            page = self.paginate_queryset(qs)
        except NotFound:
            return Response(
                {
                    "count": qs.count(),
                    "next": None,
                    "previous": None,
                    "results": [],
                }
            )

        serializer = TestimonyProfileHeaderSerializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        results = [
            item for item in serializer.data
            if item is not None
        ]

        return self.get_paginated_response(results)

    # -------------------------------------------------
    # Explore (public discover)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Profile summary - one per testimony type
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Owner-only testimony summary.

        Backward-compatible contract for web:
        {
            audio:   { exists: true/false, ...payload },
            video:   { exists: true/false, ...payload },
            written: { exists: true/false, ...payload },
        }

        Testimony is Member-only, so owner is always request.user.member_profile.
        """
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
            Testimony.objects
            .filter(
                content_type_id=owner_ct.id,
                object_id=owner.id,
                is_active=True,
            )
            .only(
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
                "audio_artwork",
                "media_assets",

                # Visibility / UI.
                "visibility",
                "is_hidden",

                # Timestamps / pipeline.
                "published_at",
                "updated_at",
                "is_converted",

                # Ownership for owner action detection.
                "content_type_id",
                "object_id",
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
                context={
                    "request": request,
                },
            ).data

            if not data:
                return empty_payload(ttype)

            # -------------------------------------------------
            # Backward-compatible web contract
            # -------------------------------------------------
            data["exists"] = True
            data["converting"] = bool(
                item.type in (Testimony.TYPE_VIDEO, Testimony.TYPE_AUDIO)
                and not item.is_converted
            )
            data["ready_status"] = "done" if item.is_converted else None
            data["job_id"] = None

            # Older frontend aliases.
            if item.type == Testimony.TYPE_AUDIO:
                data["audio_key"] = getattr(item.audio, "name", None)
                data["audio_artwork_key"] = getattr(
                    item.audio_artwork,
                    "name",
                    None,
                )

            if item.type == Testimony.TYPE_VIDEO:
                data["video_key"] = getattr(item.video, "name", None)
                data["thumbnail_key"] = getattr(item.thumbnail, "name", None)

            if item.type == Testimony.TYPE_WRITTEN:
                content = getattr(item, "content", "") or ""
                data["excerpt"] = (
                    content[:140] + "…"
                    if len(content) > 140
                    else content
                )

            # Owner menu support, even if serializer shape changes later.
            data["owner"] = {
                "type": "member",
                "id": owner.id,
                "is_me": True,
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

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _resolve_owner_object(self, obj):
        """
        Resolve owner object from (content_type, object_id).

        Returns model instance (e.g., Member / Organization / CustomUser)
        or None.
        """
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
        """
        Normalize owner into:
        - owner_user: CustomUser or None
        - owner_member: Member or None
        - owner_obj: raw resolved owner object
        """
        owner_obj = self._resolve_owner_object(obj)

        if not owner_obj:
            return None, None, None

        # Case A) owner is Member -> user lives on member.user.
        if hasattr(owner_obj, "user"):
            owner_user = getattr(owner_obj, "user", None)
            owner_member = owner_obj
            return owner_user, owner_member, owner_obj

        # Case B) owner is CustomUser directly -> member is user.member_profile.
        try:
            from apps.accounts.models.user import CustomUser

            if isinstance(owner_obj, CustomUser):
                owner_user = owner_obj
                owner_member = getattr(owner_user, "member_profile", None)
                return owner_user, owner_member, owner_obj

        except Exception:
            logger.exception("CustomUser import/type check failed")

        # Other owners (Organization, GuestUser, etc.)
        return None, None, owner_obj

    def _profile_gate_payload(self, owner_user, reason):
        """
        Build a stable profile_gate contract for frontend.
        """
        return {
            "profile_gate": {
                "key": "profile_privacy_redirect",
                "reason": reason,
                "redirect_to": f"/lit/{owner_user.username}",
            }
        }

    def _safe_is_friend(self, viewer, owner_user):
        """
        Safe friend check: uses self._is_friend if present.
        """
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
        """
        Safe confidant check: uses self._is_confidant if present.
        """
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
        """
        Apply profile-level gates based on owner's Member/CustomUser flags.

        Rules:
        - is_deleted              -> 404
        - is_suspended            -> 200 + profile_gate
        - is_account_paused       -> 200 + profile_gate
        - is_hidden_by_confidants -> 200 + profile_gate unless confidant
        - is_privacy              -> 200 + profile_gate unless friend
        """
        viewer = request.user if request.user.is_authenticated else None
        owner_user, owner_member, owner_obj = (
            self._resolve_owner_user_and_member(obj)
        )

        # Only when we have a real owner user for redirect URL.
        if not owner_user:
            return None

        # If we don't have Member, we can't read member flags.
        if not owner_member:
            return None

        # Owner can always view their own content.
        if viewer and viewer.is_authenticated and viewer.id == owner_user.id:
            return None

        # 1) Hard deleted -> pretend not found.
        if getattr(owner_user, "is_deleted", False):
            return Response(
                {
                    "detail": "Not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2) Suspended -> limited + gate.
        if getattr(owner_user, "is_suspended", False):
            return Response(
                self._profile_gate_payload(
                    owner_user,
                    reason="account_suspended",
                ),
                status=status.HTTP_200_OK,
            )

        # 3) Paused -> limited + gate.
        if getattr(owner_user, "is_account_paused", False):
            return Response(
                self._profile_gate_payload(
                    owner_user,
                    reason="account_paused",
                ),
                status=status.HTTP_200_OK,
            )

        # 4) Hidden by confidants -> gate unless confidant.
        if getattr(owner_member, "is_hidden_by_confidants", False):
            if self._safe_is_confidant(viewer, owner_member):
                return None

            return Response(
                self._profile_gate_payload(
                    owner_user,
                    reason="hidden_by_confidants",
                ),
                status=status.HTTP_200_OK,
            )

        # 5) Privacy -> gate unless friend.
        if getattr(owner_member, "is_privacy", False):
            if self._safe_is_friend(viewer, owner_user):
                return None

            return Response(
                self._profile_gate_payload(
                    owner_user,
                    reason="private_profile",
                ),
                status=status.HTTP_200_OK,
            )

        return None

    # -------------------------------------------------
    # Retrieve (public-safe, analytics counted)
    # -------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        # -------------------------------------------------
        # 0) HARD owner-level gate
        # -------------------------------------------------
        # Covers:
        # - user.is_deleted
        # - user.is_suspended
        # - member.is_hidden_by_confidants
        self.apply_hard_owner_gate(request, obj)

        # -------------------------------------------------
        # 0.5) SOFT profile privacy gate
        # -------------------------------------------------
        # Covers:
        # - member.is_privacy
        redirect_response = self.apply_profile_privacy_gate(request, obj)

        if redirect_response:
            return redirect_response

        # -------------------------------------------------
        # 1) Visibility gate
        # -------------------------------------------------
        reason = VisibilityPolicy.gate_reason(
            viewer=request.user,
            obj=obj,
        )

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

        # -------------------------------------------------
        # 2) Analytics
        # -------------------------------------------------
        try:
            Testimony.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("testimony analytics update failed")

        # -------------------------------------------------
        # 3) Normal response
        # -------------------------------------------------
        serializer = self.get_serializer(obj)
        return Response(serializer.data)