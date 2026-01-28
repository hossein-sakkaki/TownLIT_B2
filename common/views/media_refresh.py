# common/views/media_refresh.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from common.aws.s3_utils import generate_presigned_url

import logging

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_media_url(request):
    """
    Refresh a presigned S3 URL for an existing private object.

    Expected payload:
    {
        "key": "posts/videos/moment/....mp4"
    }
    """

    key = request.data.get("key")

    if not key:
        return Response(
            {"detail": "Missing 'key'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        url = generate_presigned_url(key)
        if not url:
            return Response(
                {"detail": "Unable to refresh media URL."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "url": url,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception(f"Media URL refresh failed for key={key}")
        return Response(
            {"detail": "Internal error while refreshing media URL."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
