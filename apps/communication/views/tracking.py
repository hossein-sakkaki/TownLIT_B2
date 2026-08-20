# apps/communication/views/tracking.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


import base64

from django.core import signing
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.views import View

from apps.communication.models import EmailLog
from apps.communication.services import (
    EmailAnalyticsService,
    EmailTrackingService,
)


TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
)


class EmailOpenTrackingView(View):
    def get(self, request, token):
        tracking = EmailTrackingService()

        try:
            delivery_id = tracking.resolve_open_token(token)

            if EmailLog.objects.filter(pk=delivery_id).exists():
                EmailAnalyticsService().record_open(
                    delivery_id=delivery_id,
                    request=request,
                )
        except Exception:
            # Tracking pixels should never break email rendering.
            pass

        response = HttpResponse(
            TRANSPARENT_GIF,
            content_type="image/gif",
        )
        response["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response


class EmailClickTrackingView(View):
    def get(self, request, token):
        tracking = EmailTrackingService()

        try:
            delivery_id, target_url = tracking.resolve_click_token(token)
        except signing.BadSignature as error:
            raise Http404("Invalid email tracking link.") from error

        if not EmailLog.objects.filter(pk=delivery_id).exists():
            raise Http404("Email delivery not found.")

        EmailAnalyticsService().record_click(
            delivery_id=delivery_id,
            url=target_url,
            request=request,
        )

        return redirect(target_url)