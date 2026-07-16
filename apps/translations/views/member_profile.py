# apps/translations/views/member_profile.py

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError

from apps.profiles.models.member import Member


class MemberProfileTranslationViewSet(viewsets.ViewSet):
    """
    Translation actions for public member-profile story fields.

    Lookup value:
        username

    Routes:
        POST /translations/member-profiles/<username>/translate-biography/
        POST /translations/member-profiles/<username>/translate-vision/
    """

    lookup_field = "username"
    lookup_url_kwarg = "username"

    def get_object(self):
        username = self.kwargs["username"]

        return get_object_or_404(
            Member.objects.select_related("user"),
            user__username__iexact=username,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="translate-biography",
    )
    def translate_biography(self, request, username=None):
        profile = self.get_object()

        denial = self._visibility_denial(
            profile=profile,
            request=request,
        )

        if denial is not None:
            return denial

        return self._translate_field(
            request=request,
            profile=profile,
            field_name="biography",
            empty_message="Biography is empty.",
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="translate-vision",
    )
    def translate_vision(self, request, username=None):
        profile = self.get_object()

        denial = self._visibility_denial(
            profile=profile,
            request=request,
        )

        if denial is not None:
            return denial

        return self._translate_field(
            request=request,
            profile=profile,
            field_name="vision",
            empty_message="Vision is empty.",
        )

    def _translate_field(
        self,
        *,
        request,
        profile,
        field_name,
        empty_message,
    ):
        source_text = getattr(
            profile,
            field_name,
            None,
        )

        if not source_text or not source_text.strip():
            return Response(
                {
                    "detail": empty_message,
                    "code": "empty_source_text",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_language = request.data.get(
            "target_language"
        )

        try:
            result = translate_cached(
                obj=profile,
                field_name=field_name,
                user=request.user,
                target_language=target_language,
            )
        except EmptySourceTextError:
            return Response(
                {
                    "detail": "Source text is empty.",
                    "code": "empty_source_text",
                },
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

    def _visibility_denial(
        self,
        *,
        profile,
        request,
    ):
        """
        Keep this aligned with the exact public profile gate used by
        VisitorProfileAPI.

        The profile endpoint must remain the source of truth for whether the
        current visitor may read biography and vision.
        """

        reason = None

        try:
            reason = profile.visibility_gate_reason(
                request.user
            )
        except AttributeError:
            reason = None

        if reason:
            return Response(
                {
                    "detail": "Access restricted.",
                    "code": reason,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return None

