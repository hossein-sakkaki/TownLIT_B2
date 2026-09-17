# apps/posts/views/share_preview.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-17.
# Last Update by Hossein Sakkaki on 2026-09-17.

from __future__ import annotations

import logging
import mimetypes

from pathlib import Path

from django.core.files.storage import (
    default_storage,
)
from django.http import FileResponse

from rest_framework import status
from rest_framework.permissions import (
    AllowAny,
)
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.posts.services.share_preview import (
    resolve_post_share_preview,
)


logger = logging.getLogger(
    __name__
)


class PostSharePreviewView(
    APIView
):
    """
    Public crawler-safe metadata for share cards.

    No protected media, interaction data, analytics or
    non-public content is exposed here.
    """

    permission_classes = [
        AllowAny,
    ]
    authentication_classes = []

    def get(
        self,
        request,
        kind: str,
        slug: str,
    ):
        preview = (
            resolve_post_share_preview(
                kind=kind,
                slug=slug,
                viewer=request.user,
            )
        )

        if preview is None:
            return Response(
                {
                    "detail":
                        "Share preview not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        image_url = None

        if preview.image_key:
            image_url = reverse(
                "posts:share-preview-image",
                kwargs={
                    "kind":
                        preview.kind,
                    "slug":
                        preview.slug,
                },
                request=request,
            )

        response = Response(
            {
                "kind":
                    preview.kind,
                "id":
                    preview.object_id,
                "slug":
                    preview.slug,
                "title":
                    preview.title,
                "description":
                    preview.description,
                "canonical_path":
                    preview.canonical_path,
                "image":
                    (
                        {
                            "url":
                                image_url,
                            "alt":
                                preview.image_alt,
                        }
                        if image_url
                        else None
                    ),
            },
            status=status.HTTP_200_OK,
        )

        response[
            "Cache-Control"
        ] = (
            "public, max-age=300, "
            "stale-while-revalidate=3600"
        )

        return response


class PostSharePreviewImageView(
    APIView
):
    """
    Stable image-only endpoint for public share cards.

    Audio and video files are never exposed through this route.
    """

    permission_classes = [
        AllowAny,
    ]
    authentication_classes = []

    def get(
        self,
        request,
        kind: str,
        slug: str,
    ):
        preview = (
            resolve_post_share_preview(
                kind=kind,
                slug=slug,
                viewer=request.user,
            )
        )

        if (
            preview is None
            or not preview.image_key
        ):
            return Response(
                {
                    "detail":
                        "Share preview image not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        key = preview.image_key

        try:
            file_handle = (
                default_storage.open(
                    key,
                    "rb",
                )
            )
        except Exception:
            logger.exception(
                "posts.share_preview_image_open_failed "
                "kind=%s slug=%s key=%s",
                preview.kind,
                preview.slug,
                key,
            )

            return Response(
                {
                    "detail":
                        "Share preview image not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        content_type = (
            mimetypes.guess_type(
                key
            )[0]
            or "image/jpeg"
        )

        suffix = (
            Path(key).suffix
            or ".jpg"
        )

        response = FileResponse(
            file_handle,
            as_attachment=False,
            filename=(
                f"{preview.kind}-"
                f"{preview.object_id}"
                f"{suffix}"
            ),
            content_type=content_type,
        )

        response[
            "Cache-Control"
        ] = (
            "public, max-age=3600, "
            "stale-while-revalidate=86400"
        )

        response[
            "X-Content-Type-Options"
        ] = "nosniff"

        return response