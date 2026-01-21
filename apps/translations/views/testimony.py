# apps/translations/views/testimony.py

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.posts.models.testimony import Testimony
from apps.core.visibility.policy import VisibilityPolicy
from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError
from apps.translations.serializers import TranslationRequestSerializer

logger = logging.getLogger(__name__)


class TestimonyTranslationViewSet(viewsets.ViewSet):
    """
    Translation endpoint for written testimonies.
    Handles anonymous + authenticated viewers safely.
    """

    lookup_field = "slug"

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def get_object(self):
        slug = self.kwargs.get("slug")
        logger.debug("[translation] resolving testimony slug=%s", slug)
        return get_object_or_404(Testimony, slug=slug)

    # -------------------------------------------------
    # Actions
    # -------------------------------------------------
    @action(detail=True, methods=["post"], url_path="translate")
    def translate(self, request, slug=None):
        logger.info(
            "[translation] request start slug=%s viewer=%s",
            slug,
            request.user if request.user.is_authenticated else "anonymous",
        )

        testimony = self.get_object()

        # -------------------------------------------------
        # 1) Type gate
        # -------------------------------------------------
        if testimony.type != Testimony.TYPE_WRITTEN:
            logger.warning(
                "[translation] rejected: non-written testimony id=%s type=%s",
                testimony.id,
                testimony.type,
            )
            return Response(
                {"detail": "Translation allowed for written testimonies only."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # 2) Visibility gate (single source of truth)
        # -------------------------------------------------
        try:
            gate_reason = VisibilityPolicy.gate_reason(
                viewer=request.user,
                obj=testimony,
            )
        except Exception:
            logger.exception(
                "[translation] visibility gate crashed testimony_id=%s",
                testimony.id,
            )
            return Response(
                {"detail": "Visibility check failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if gate_reason:
            logger.info(
                "[translation] visibility denied testimony_id=%s reason=%s viewer=%s",
                testimony.id,
                gate_reason,
                request.user if request.user.is_authenticated else "anonymous",
            )
            return Response(
                {"detail": "Access restricted.", "code": gate_reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        # -------------------------------------------------
        # 3) Validate request payload
        # -------------------------------------------------
        ser = TranslationRequestSerializer(data=request.data or {})
        if not ser.is_valid():
            logger.warning(
                "[translation] invalid payload testimony_id=%s errors=%s",
                testimony.id,
                ser.errors,
            )
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        target_language = ser.validated_data.get("target_language")
        logger.debug(
            "[translation] target_language=%s testimony_id=%s",
            target_language,
            testimony.id,
        )

        # Normalize viewer for translation layer
        viewer_user = request.user if request.user.is_authenticated else None

        # -------------------------------------------------
        # 4) Translation execution
        # -------------------------------------------------
        try:
            logger.debug(
                "[translation] translating title testimony_id=%s",
                testimony.id,
            )
            title_result = translate_cached(
                obj=testimony,
                field_name="title",
                user=viewer_user,
                target_language=target_language,
            )

            logger.debug(
                "[translation] translating content testimony_id=%s",
                testimony.id,
            )
            content_result = translate_cached(
                obj=testimony,
                field_name="content",
                user=viewer_user,
                target_language=target_language,
            )

        except EmptySourceTextError:
            logger.info(
                "[translation] empty source text testimony_id=%s",
                testimony.id,
            )
            return Response(
                {"detail": "Source text is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception(
                "[translation] translate_cached failed testimony_id=%s error=%s",
                testimony.id,
                exc,
            )
            return Response(
                {"detail": "Translation service error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -------------------------------------------------
        # 5) Success response
        # -------------------------------------------------
        logger.info(
            "[translation] success testimony_id=%s target_language=%s cached=%s",
            testimony.id,
            title_result.get("target_language"),
            bool(title_result.get("cached")) and bool(content_result.get("cached")),
        )

        return Response(
            {
                "title": title_result["text"],
                "content": content_result["text"],
                "target_language": title_result["target_language"],
                "cached": bool(title_result.get("cached"))
                and bool(content_result.get("cached")),
            },
            status=status.HTTP_200_OK,
        )
