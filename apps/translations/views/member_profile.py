# apps/translations/views/member_profile.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki (original creation date not recorded in source).
# Last Update by Hossein Sakkaki on 2026-11-09.

"""Existing member-profile translation routes with profile visibility enforcement."""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.profiles.models.member import Member
from apps.profiles.views.visitor_profile import VisitorProfileViewSet
from apps.translations.services.base import translate_cached
from apps.translations.services.exceptions import EmptySourceTextError

logger = logging.getLogger(__name__)


class MemberProfileTranslationViewSet(viewsets.ViewSet):
    """Translate authorized Biography and Vision through the existing cache."""

    lookup_field = "username"
    lookup_url_kwarg = "username"

    def get_object(self):
        return get_object_or_404(
            Member.objects.select_related("user"),
            user__username__iexact=self.kwargs["username"],
            is_active=True,
            user__is_active=True,
        )

    @action(detail=True, methods=["post"], url_path="translate-biography")
    def translate_biography(self, request, username=None):
        profile = self.get_object()
        denial = self._visibility_denial(profile=profile, request=request)
        if denial is not None:
            return denial
        return self._translate_field(
            request=request,
            profile=profile,
            field_name="biography",
            empty_message="Biography is empty.",
        )

    @action(detail=True, methods=["post"], url_path="translate-vision")
    def translate_vision(self, request, username=None):
        profile = self.get_object()
        denial = self._visibility_denial(profile=profile, request=request)
        if denial is not None:
            return denial
        return self._translate_field(
            request=request,
            profile=profile,
            field_name="vision",
            empty_message="Vision is empty.",
        )

    def _translate_field(self, *, request, profile, field_name, empty_message):
        source_text = getattr(profile, field_name, None)
        if not source_text or not source_text.strip():
            return Response(
                {"detail": empty_message, "code": "empty_source_text"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = translate_cached(
                obj=profile,
                field_name=field_name,
                user=request.user,
                target_language=request.data.get("target_language"),
            )
        except EmptySourceTextError:
            return Response(
                {"detail": "Source text is empty.", "code": "empty_source_text"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "content": result["text"],
                "target_language": result["target_language"],
                "cached": result["cached"],
                "source_language": result.get("source_language") or None,
            },
            status=status.HTTP_200_OK,
        )

    def _visibility_denial(self, *, profile, request):
        """Enforce the visitor profile content gate, failing closed on errors."""
        denial = Response(
            {"detail": "Access restricted.", "code": "profile_unavailable"},
            status=status.HTTP_403_FORBIDDEN,
        )

        try:
            owner = profile.user
            request_user = request.user
            viewer = (
                request_user
                if getattr(request_user, "is_authenticated", False)
                else None
            )

            # VisitorProfileViewSet's boundary helper can suppress policy errors.
            if viewer is not None and viewer.pk != owner.pk:
                if BoundaryPolicy.has_boundary_between(viewer, owner):
                    return denial

            visitor_view = VisitorProfileViewSet()
            blocked = visitor_view._profile_content_gate_response(
                request=request,
                profile=profile,
                user=owner,
                profile_type="member",
            )
            return denial if blocked is not None else None
        except Exception:
            logger.exception(
                "member_profile_translation_access_check_failed profile_id=%s",
                getattr(profile, "pk", None),
            )
            return denial
