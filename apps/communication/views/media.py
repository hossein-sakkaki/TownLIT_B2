# apps/communication/views/media.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.

from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from apps.communication.models import EmailCampaign
from apps.communication.services.media import (
    EmailMediaUploadError,
    EmailMediaUploadService,
)


@require_POST
def email_media_upload(request):
    user = request.user

    if (
        not user.is_authenticated
        or not user.is_active
        or not user.is_staff
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Staff access is required.",
            },
            status=403,
        )

    if not user.has_perm(
        "communication.change_emailcampaign"
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "You do not have permission "
                    "to edit email campaigns."
                ),
            },
            status=403,
        )

    campaign_id = request.POST.get(
        "campaign_id"
    )

    try:
        campaign_id = int(
            campaign_id
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid campaign.",
            },
            status=400,
        )

    campaign = get_object_or_404(
        EmailCampaign,
        pk=campaign_id,
    )

    if not campaign.can_edit_content:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "This campaign can no longer "
                    "be edited."
                ),
            },
            status=409,
        )

    uploaded_file = request.FILES.get(
        "image"
    )

    try:
        result = (
            EmailMediaUploadService()
            .upload_campaign_image(
                campaign_id=campaign.pk,
                uploaded_file=uploaded_file,
            )
        )

    except EmailMediaUploadError as exc:
        return JsonResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "url": result.url,
            "key": result.key,
            "width": result.width,
            "height": result.height,
            "file_size": result.file_size,
        }
    )