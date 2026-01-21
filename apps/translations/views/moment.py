# apps/translations/views/moment.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.posts.models.moment import Moment
from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError


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
        reason = None
        try:
            reason = moment.visibility_gate_reason(request.user)
        except Exception:
            pass

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
