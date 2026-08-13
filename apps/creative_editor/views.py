# apps/creative_editor/views.py

from __future__ import annotations

import logging

from django.db.models import Prefetch
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.creative_editor.models import (
    CreativeBackgroundPreset,
    CreativeComposition,
    CreativeCompositionMedia,
    CreativeFont,
    CreativeRenderJob,
    StickerAsset,
    StickerPack,
)
from apps.creative_editor.serializers import (
    CreativeBackgroundPresetSerializer,
    CreativeCompositionMediaSerializer,
    CreativeCompositionMediaWriteSerializer,
    CreativeCompositionSerializer,
    CreativeCompositionWriteSerializer,
    CreativeEditorBootstrapSerializer,
    CreativeFontSerializer,
    CreativeRenderJobSerializer,
    StickerPackSerializer,
)
from apps.creative_editor.services.media import (
    archive_composition_media,
)
from apps.creative_editor.services.compositions import (
    CreativeRevisionConflict,
    archive_composition,
    request_render,
)
from apps.creative_editor.services.video_policy import (
    get_creative_video_policy,
)
from apps.creative_editor.validators.document import (
    DOCUMENT_VERSION,
    LEGACY_DOCUMENT_VERSION,
    MAX_DOCUMENT_BYTES,
    MAX_IMAGE_LAYERS,
    MAX_LAYERS,
    MAX_MEDIA_LAYERS,
    MAX_STICKER_LAYERS,
    MAX_TEXT_CHARACTERS,
    MAX_TEXT_LAYERS,
    MAX_VIDEO_LAYERS,
)


logger = logging.getLogger(__name__)


class CreativeCompositionCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
    ordering = ("-updated_at", "-id")


class CreativeCompositionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    User-owned creative compositions.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CreativeCompositionCursorPagination

    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    http_method_names = [
        "get",
        "post",
        "put",
        "patch",
        "head",
        "options",
    ]

    def get_queryset(self):
        queryset = (
            CreativeComposition.objects.filter(
                owner=self.request.user,
            )
            .select_related("source_content_type")
        )

        include_archived = (
            self.request.query_params.get(
                "include_archived",
                "",
            )
            .strip()
            .lower()
            in {"1", "true", "yes"}
        )

        if not include_archived:
            queryset = queryset.filter(is_active=True)

        status_value = self.request.query_params.get(
            "status",
            "",
        ).strip()

        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset

    def get_serializer_class(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
        }:
            return CreativeCompositionWriteSerializer

        return CreativeCompositionSerializer

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(
                (
                    "creative_editor.composition.create.invalid "
                    "user_id=%s "
                    "content_type=%s "
                    "keys=%s "
                    "source_mode=%r "
                    "errors=%s"
                ),
                getattr(request.user, "pk", None),
                request.content_type,
                sorted(str(key) for key in request.data.keys()),
                request.data.get("source_mode"),
                serializer.errors,
            )

            return Response(
                {
                    "detail": "Creative composition data is invalid.",
                    "code": "creative_composition_invalid",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        composition = serializer.save()

        response = CreativeCompositionSerializer(
            composition,
            context={"request": request},
        )

        return Response(
            response.data,
            status=status.HTTP_201_CREATED,
        )

    def update(
        self,
        request,
        *args,
        **kwargs,
    ):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )

        if not serializer.is_valid():
            logger.warning(
                (
                    "creative_editor.composition.update.invalid "
                    "user_id=%s "
                    "composition_id=%s "
                    "current_revision=%s "
                    "content_type=%s "
                    "keys=%s "
                    "source_mode=%r "
                    "expected_revision=%r "
                    "errors=%s"
                ),
                getattr(request.user, "pk", None),
                getattr(instance, "public_id", None),
                getattr(instance, "revision", None),
                request.content_type,
                sorted(str(key) for key in request.data.keys()),
                request.data.get("source_mode"),
                request.data.get("expected_revision"),
                serializer.errors,
            )

            return Response(
                {
                    "detail": "Creative composition data is invalid.",
                    "code": "creative_composition_invalid",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            composition = serializer.save()
        except CreativeRevisionConflict as exc:
            logger.warning(
                (
                    "creative_editor.composition.update.conflict "
                    "user_id=%s "
                    "composition_id=%s "
                    "expected_revision=%s "
                    "current_revision=%s"
                ),
                getattr(request.user, "pk", None),
                getattr(instance, "public_id", None),
                exc.expected_revision,
                exc.current_revision,
            )

            return Response(
                {
                    "detail": "Composition revision conflict.",
                    "code": "revision_conflict",
                    "expected_revision": exc.expected_revision,
                    "current_revision": exc.current_revision,
                },
                status=status.HTTP_409_CONFLICT,
            )

        response = CreativeCompositionSerializer(
            composition,
            context={"request": request},
        )

        return Response(
            response.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="bootstrap",
    )
    def bootstrap(self, request):
        consumer = (
            request.query_params.get(
                "consumer",
                "",
            )
            .strip()
            .lower()
        )

        video_policy = get_creative_video_policy()
        fonts = CreativeFont.objects.filter(
            is_active=True,
            is_user_selectable=True,
        ).order_by(
            "sort_order",
            "display_name",
            "id",
        )

        fallback_fonts = CreativeFont.objects.filter(
            is_active=True,
            is_user_selectable=False,
            source=CreativeFont.Source.BUNDLED,
        ).order_by(
            "sort_order",
            "display_name",
            "id",
        )

        sticker_queryset = StickerAsset.objects.filter(
            is_active=True,
            is_converted=True,
        ).order_by(
            "sort_order",
            "title",
            "id",
        )

        packs = (
            StickerPack.objects.filter(
                is_active=True,
            )
            .order_by(
                "sort_order",
                "name",
                "id",
            )
            .prefetch_related(
                Prefetch(
                    "stickers",
                    queryset=sticker_queryset,
                )
            )
        )

        background_queryset = (
            CreativeBackgroundPreset.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "sort_order",
                "title",
                "id",
            )
        )

        backgrounds = [
            background
            for background in background_queryset
            if (
                not consumer
                or background.supports_consumer(
                    consumer
                )
            )
        ]

        payload = {
            "fonts": CreativeFontSerializer(
                fonts,
                many=True,
                context={"request": request},
            ).data,
            "fallback_fonts": CreativeFontSerializer(
                fallback_fonts,
                many=True,
                context={"request": request},
            ).data,
            "sticker_packs": StickerPackSerializer(
                packs,
                many=True,
                context={"request": request},
            ).data,
            "backgrounds": (
                CreativeBackgroundPresetSerializer(
                    backgrounds,
                    many=True,
                    context={
                        "request": request,
                    },
                ).data
            ),
            "limits": {
                "document_version": DOCUMENT_VERSION,
                "legacy_document_version": LEGACY_DOCUMENT_VERSION,
                "max_document_bytes": MAX_DOCUMENT_BYTES,
                "max_layers": MAX_LAYERS,
                "max_text_layers": MAX_TEXT_LAYERS,
                "max_sticker_layers": MAX_STICKER_LAYERS,
                "max_image_layers": MAX_IMAGE_LAYERS,
                "max_media_layers": MAX_MEDIA_LAYERS,
                "max_text_characters": MAX_TEXT_CHARACTERS,
                "max_canvas_width": 8192,
                "max_canvas_height": 8192,
                "max_video_layers": MAX_VIDEO_LAYERS,
                "min_video_duration_ms": video_policy.minimum_duration_ms,
                "max_video_duration_ms": video_policy.maximum_duration_ms,
            },
            "capabilities": {
                "document_v2": True,
                "text": True,
                "stickers": True,
                "solid_background": True,
                "gradient_background": True,
                "server_background_catalog": True,

                # Legacy v1 source support.
                "uploaded_image": True,
                "content_reference": True,

                # Media Architecture v2.
                "composition_media": True,
                "image_layers": True,
                "multiple_images": True,
                "media_crop": True,
                "media_fit": True,

                "font_fallbacks": True,
                "mixed_script_text": True,
                "emoji_text": True,
                "hashtags": False,
                "mentions": False,
                "animated_stickers": False,
                "drawing": False,
                "shapes": False,
                
                "video_layers": True,
                "video_upload": True,
                "video_trim": True,
                "video_render": True,
            },
        }

        return Response(
            payload,
            status=status.HTTP_200_OK,
        )
    
    @action(
        detail=True,
        methods=["post"],
        url_path="render",
    )
    def render(
        self,
        request,
        public_id=None,
    ):
        composition = self.get_object()
        requested_revision = request.data.get("revision")

        if requested_revision is None:
            raise DRFValidationError(
                {
                    "revision": (
                        "Current composition revision is required."
                    ),
                }
            )

        try:
            requested_revision = int(requested_revision)
        except (TypeError, ValueError):
            raise DRFValidationError(
                {
                    "revision": "Revision must be an integer.",
                }
            )

        if requested_revision != composition.revision:
            return Response(
                {
                    "detail": "Composition revision conflict.",
                    "code": "revision_conflict",
                    "expected_revision": requested_revision,
                    "current_revision": composition.revision,
                },
                status=status.HTTP_409_CONFLICT,
            )
    
        result = request_render(
            composition=composition,
        )

        output = CreativeRenderJobSerializer(
            result.job,
            context={"request": request},
        )

        return Response(
            output.data,
            status=(
                status.HTTP_201_CREATED
                if result.created
                else status.HTTP_200_OK
            ),
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="render-jobs",
    )
    def render_jobs(
        self,
        request,
        public_id=None,
    ):
        composition = self.get_object()

        jobs = composition.render_jobs.all().order_by(
            "-created_at",
            "-id",
        )[:20]

        return Response(
            CreativeRenderJobSerializer(
                jobs,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="archive",
    )
    def archive(
        self,
        request,
        public_id=None,
    ):
        composition = self.get_object()

        archived = archive_composition(
            composition=composition,
        )

        return Response(
            CreativeCompositionSerializer(
                archived,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="media-assets",
    )
    def media_assets(
        self,
        request,
        public_id=None,
    ):
        """
        List or idempotently create composition media.

        A client-supplied media UUID allows the editor to
        establish stable layer identity before upload finishes.
        """

        composition = self.get_object()

        if request.method == "GET":
            queryset = (
                CreativeCompositionMedia.objects
                .filter(
                    composition=composition,
                    is_active=True,
                )
                .select_related(
                    "source_content_type"
                )
                .order_by(
                    "created_at",
                    "id",
                )
            )

            return Response(
                CreativeCompositionMediaSerializer(
                    queryset,
                    many=True,
                    context={
                        "request": request,
                    },
                ).data,
                status=status.HTTP_200_OK,
            )

        serializer = CreativeCompositionMediaWriteSerializer(
            data=request.data,
            context={
                "request": request,
                "composition": composition,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        client_public_id = serializer.validated_data.get(
            "public_id"
        )

        if client_public_id is not None:
            existing = (
                CreativeCompositionMedia.objects
                .filter(
                    public_id=client_public_id,
                )
                .select_related(
                    "source_content_type",
                    "composition",
                )
                .first()
            )

            if existing is not None:
                if existing.composition_id != composition.pk:
                    return Response(
                        {
                            "detail": (
                                "Creative media id is already "
                                "owned by another composition."
                            ),
                            "code": "creative_media_id_conflict",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                requested_media_type = (
                    serializer.validated_data.get(
                        "media_type",
                        CreativeCompositionMedia.MediaType.IMAGE,
                    )
                )

                requested_source_mode = (
                    serializer.validated_data.get(
                        "source_mode",
                        CreativeCompositionMedia.SourceMode.UPLOAD,
                    )
                )

                if (
                    existing.media_type != requested_media_type
                    or existing.source_mode != requested_source_mode
                ):
                    return Response(
                        {
                            "detail": (
                                "Creative media id was already used "
                                "for a different media source."
                            ),
                            "code": "creative_media_id_conflict",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                if not existing.is_active:
                    return Response(
                        {
                            "detail": (
                                "Creative media id belongs to "
                                "an archived media asset."
                            ),
                            "code": "creative_media_archived",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                return Response(
                    CreativeCompositionMediaSerializer(
                        existing,
                        context={
                            "request": request,
                        },
                    ).data,
                    status=status.HTTP_200_OK,
                )

        media = serializer.save()

        return Response(
            CreativeCompositionMediaSerializer(
                media,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_201_CREATED,
        )
        
    @action(
        detail=True,
        methods=["get"],
        url_path=(
            r"media-assets/"
            r"(?P<media_id>[0-9a-fA-F-]{36})"
        ),
    )
    def media_asset_detail(
        self,
        request,
        public_id=None,
        media_id=None,
    ):
        """
        Retrieve one composition media item.
        """

        composition = self.get_object()

        media = (
            CreativeCompositionMedia.objects
            .filter(
                composition=composition,
                public_id=media_id,
            )
            .select_related(
                "source_content_type"
            )
            .first()
        )

        if media is None:
            return Response(
                {
                    "detail": (
                        "Creative composition media "
                        "was not found."
                    ),
                    "code": "creative_media_not_found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            CreativeCompositionMediaSerializer(
                media,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path=(
            r"media-assets/"
            r"(?P<media_id>[0-9a-fA-F-]{36})/"
            r"archive"
        ),
    )
    def media_asset_archive(
        self,
        request,
        public_id=None,
        media_id=None,
    ):
        """
        Archive unreferenced composition media.
        """

        composition = self.get_object()

        media = (
            CreativeCompositionMedia.objects
            .filter(
                composition=composition,
                public_id=media_id,
            )
            .select_related(
                "composition"
            )
            .first()
        )

        if media is None:
            return Response(
                {
                    "detail": (
                        "Creative composition media "
                        "was not found."
                    ),
                    "code": "creative_media_not_found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            archived = archive_composition_media(
                media=media
            )

        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": (
                        "Creative media cannot be archived."
                    ),
                    "code": "creative_media_in_use",
                    "errors": (
                        exc.message_dict
                        if hasattr(
                            exc,
                            "message_dict",
                        )
                        else exc.messages
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            CreativeCompositionMediaSerializer(
                archived,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

class CreativeRenderJobViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only access to user-owned render jobs.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CreativeRenderJobSerializer

    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    http_method_names = [
        "get",
        "head",
        "options",
    ]

    def get_queryset(self):
        return (
            CreativeRenderJob.objects.filter(
                composition__owner=self.request.user,
            )
            .select_related("composition")
        )