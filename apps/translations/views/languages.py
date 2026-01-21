# apps/translations/views/languages.py
import logging
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.translations.services.supported_languages import get_supported_languages

logger = logging.getLogger(__name__)


class TranslationMetaViewSet(viewsets.ViewSet):
    """
    Metadata endpoints for translation (shared by web/iOS/android).
    """

    @action(detail=False, methods=["get"], url_path="languages")
    def languages(self, request):
        try:
            langs = get_supported_languages()
            return Response({"languages": langs}, status=status.HTTP_200_OK)
        except Exception:
            logger.exception("[translation-meta] languages failed")
            return Response(
                {"detail": "Failed to load supported languages."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
