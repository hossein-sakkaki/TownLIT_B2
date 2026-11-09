# apps/translations/views/moment.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-07.

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.posts.models.moment import Moment
from apps.core.visibility.policy import VisibilityPolicy
from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError


logger = logging.getLogger(__name__)


class MomentTranslationViewSet(viewsets.ViewSet):
    """
    Translation actions for moment captions.
    """

    lookup_field = "slug"

    def get_object(self):
        return get_object_or_404(
            Moment,
            slug=self.kwargs["slug"],
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="translate-caption",
    )
    def translate_caption(self, request, slug=None):
        """
        Translate moment caption.
        """

        moment = self.get_object()

        # No caption → nothing to translate
        if not moment.caption or not moment.caption.strip():
            return Response(
                {"detail": "Caption is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Respect existing visibility / permission logic
        try:
            reason = VisibilityPolicy.gate_reason(
                viewer=request.user,
                obj=moment,
            )
        except Exception:
            logger.exception(
                "moment_translation_visibility_check_failed moment_id=%s",
                moment.pk,
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
                obj=moment,
                field_name="caption",
                user=request.user,
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

