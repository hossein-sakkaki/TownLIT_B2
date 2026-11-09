# apps/translations/views/prayer.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-07.

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.posts.models.pray import Prayer
from apps.core.visibility.policy import VisibilityPolicy
from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError


logger = logging.getLogger(__name__)


class PrayerTranslationViewSet(viewsets.ViewSet):
    """
    Translation actions for prayer caption and prayer response text.
    """

    lookup_field = "slug"

    def get_object(self):
        return get_object_or_404(
            Prayer,
            slug=self.kwargs["slug"],
        )

    @action(detail=True, methods=["post"], url_path="translate-caption")
    def translate_caption(self, request, slug=None):
        prayer = self.get_object()

        # Only caption is translatable
        if not prayer.caption or not prayer.caption.strip():
            return Response(
                {"detail": "Caption is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Visibility gate
        try:
            reason = VisibilityPolicy.gate_reason(
                viewer=request.user,
                obj=prayer,
            )
        except Exception:
            logger.exception(
                "prayer_translation_visibility_check_failed prayer_id=%s",
                prayer.pk,
            )
            return Response(
                {"detail": "Visibility check unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if reason:
            return Response(
                {"detail": "Access restricted.", "code": reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_language = request.data.get("target_language")

        try:
            result = translate_cached(
                obj=prayer,
                field_name="caption",
                user=request.user if request.user.is_authenticated else None,
                target_language=target_language,
            )
        except EmptySourceTextError:
            return Response(
                {"detail": "Source text is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "caption": result["text"],
                "target_language": result["target_language"],
                "cached": result["cached"],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="translate-response")
    def translate_response(self, request, slug=None):
        prayer = self.get_object()

        # Visibility gate is based on the parent prayer.
        try:
            reason = VisibilityPolicy.gate_reason(
                viewer=request.user,
                obj=prayer,
            )
        except Exception:
            logger.exception(
                "prayer_translation_visibility_check_failed prayer_id=%s",
                prayer.pk,
            )
            return Response(
                {"detail": "Visibility check unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if reason:
            return Response(
                {"detail": "Access restricted.", "code": reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        response = getattr(prayer, "response", None)

        if not response:
            return Response(
                {"detail": "Prayer response does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not response.response_text or not response.response_text.strip():
            return Response(
                {"detail": "Response text is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_language = request.data.get("target_language")

        try:
            result = translate_cached(
                obj=response,
                field_name="response_text",
                user=request.user if request.user.is_authenticated else None,
                target_language=target_language,
            )
        except EmptySourceTextError:
            return Response(
                {"detail": "Source text is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "content": result["text"],
                "target_language": result["target_language"],
                "cached": result["cached"],
            },
            status=status.HTTP_200_OK,
        )
