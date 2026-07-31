# apps/creative_editor/views.py

from __future__ import annotations

import logging

from django.db.models import Prefetch

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
    CreativeFont,
    CreativeRenderJob,
    StickerAsset,
    StickerPack,
)
from apps.creative_editor.serializers import (
    CreativeBackgroundPresetSerializer,
    CreativeCompositionSerializer,
    CreativeCompositionWriteSerializer,
    CreativeEditorBootstrapSerializer,
    CreativeFontSerializer,
    CreativeRenderJobSerializer,
    StickerPackSerializer,
)
from apps.creative_editor.services.compositions import (
    CreativeRevisionConflict,
    archive_composition,
    request_render,
)
from apps.creative_editor.validators.document import (
    DOCUMENT_VERSION,
    MAX_DOCUMENT_BYTES,
    MAX_LAYERS,
    MAX_STICKER_LAYERS,
    MAX_TEXT_CHARACTERS,
    MAX_TEXT_LAYERS,
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

        fonts = CreativeFont.objects.filter(
            is_active=True,
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
                "max_document_bytes": MAX_DOCUMENT_BYTES,
                "max_layers": MAX_LAYERS,
                "max_text_layers": MAX_TEXT_LAYERS,
                "max_sticker_layers": MAX_STICKER_LAYERS,
                "max_text_characters": MAX_TEXT_CHARACTERS,
                "max_canvas_width": 8192,
                "max_canvas_height": 8192,
            },
            "capabilities": {
                "text": True,
                "stickers": True,
                "solid_background": True,
                "gradient_background": True,
                "server_background_catalog": True,
                "uploaded_image": True,
                "content_reference": True,
                "hashtags": False,
                "mentions": False,
                "animated_stickers": False,
                "drawing": False,
                "shapes": False,
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