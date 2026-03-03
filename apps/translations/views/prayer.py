# apps/translations/views/prayer.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.posts.models.pray import Prayer
from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError


class PrayerTranslationViewSet(viewsets.ViewSet):
    """
    Translation actions for prayer caption.
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
            reason = prayer.visibility_gate_reason(request.user)
        except Exception:
            reason = None

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