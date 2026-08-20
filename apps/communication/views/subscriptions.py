# apps/communication/views/subscriptions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.conf import settings
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from apps.communication.services import (
    EmailPreferenceService,
)
from apps.communication.services.links import (
    CommunicationURLBuilder,
)


class UnsubscribeHTMLView(View):
    def get(self, request, token):
        try:
            result = (
                EmailPreferenceService()
                .unsubscribe(
                    token,
                    request=request,
                )
            )

            resubscribe_url = (
                CommunicationURLBuilder()
                .resubscribe(
                    result.resubscribe_token
                )
            )

            return render(
                request,
                "api/communication/"
                "unsubscribe_success.html",
                {
                    "profile_url": (
                        f"{settings.FRONTEND_BASE_URL}/"
                    ),
                    "user": result.user,
                    "email": result.email,
                    "campaign": result.campaign,
                    "topic": result.topic,
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": (
                        settings.EMAIL_LOGO_URL
                    ),
                    "current_year": (
                        timezone.now().year
                    ),
                    "resubscribe_url": (
                        resubscribe_url
                    ),
                },
            )

        except Exception:
            return render(
                request,
                "api/communication/"
                "unsubscribe_failed.html",
                {
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": (
                        settings.EMAIL_LOGO_URL
                    ),
                    "current_year": (
                        timezone.now().year
                    ),
                    "support_email": (
                        settings.TOWNLIT_SUPPORT_EMAIL
                    ),
                },
                status=400,
            )


class ResubscribeView(View):
    def get(self, request, token):
        try:
            result = (
                EmailPreferenceService()
                .resubscribe(token)
            )

            return render(
                request,
                "api/communication/"
                "resubscribe_success.html",
                {
                    "profile_url": (
                        f"{settings.FRONTEND_BASE_URL}/"
                    ),
                    "user": result.user,
                    "email": result.email,
                    "first_name": (
                        getattr(
                            result.user,
                            "name",
                            "",
                        )
                        if result.user
                        else "Friend"
                    ),
                    "username": (
                        getattr(
                            result.user,
                            "username",
                            "",
                        )
                        if result.user
                        else ""
                    ),
                    "campaign": (
                        result.campaign
                    ),
                    "topic": result.topic,
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": (
                        settings.EMAIL_LOGO_URL
                    ),
                    "current_year": (
                        timezone.now().year
                    ),
                },
            )

        except Exception:
            return render(
                request,
                "api/communication/"
                "resubscribe_failed.html",
                {
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": (
                        settings.EMAIL_LOGO_URL
                    ),
                    "current_year": (
                        timezone.now().year
                    ),
                    "support_email": (
                        settings.TOWNLIT_SUPPORT_EMAIL
                    ),
                },
                status=400,
            )