# apps/communication/services/context.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.conf import settings
from django.utils import timezone

from apps.communication.constants import RE_ENGAGEMENT

from .links import CommunicationURLBuilder
from .preference_tokens import (
    ACTION_RESUBSCRIBE,
    ACTION_UNSUBSCRIBE,
    EmailPreferenceTokenService,
)


class CampaignContextBuilder:
    """
    Build recipient-safe campaign template context.
    """

    def __init__(self):
        self.token_service = (
            EmailPreferenceTokenService()
        )
        self.url_builder = (
            CommunicationURLBuilder()
        )

    def build(
        self,
        *,
        campaign,
        recipient,
        preview=False,
    ):
        context = {
            "email": recipient.email,
            "first_name": (
                recipient.first_name
                or "Friend"
            ),
            "username": (
                recipient.username
                or ""
            ),
            "user": recipient.user,
            "campaign": campaign,
            "email_theme": (
                campaign.effective_theme
            ),
            "site_domain": settings.SITE_URL,
            "logo_base_url": (
                settings.EMAIL_LOGO_URL
            ),
            "current_year": (
                timezone.now().year
            ),
            "unsubscribe_url": (
                self._preference_url(
                    campaign=campaign,
                    recipient=recipient,
                    action=ACTION_UNSUBSCRIBE,
                    preview=preview,
                )
            ),
        }

        if (
            campaign.target_group
            == RE_ENGAGEMENT
        ):
            context["resubscribe_url"] = (
                self._preference_url(
                    campaign=campaign,
                    recipient=recipient,
                    action=ACTION_RESUBSCRIBE,
                    preview=preview,
                )
            )

        return context

    def _preference_url(
        self,
        *,
        campaign,
        recipient,
        action,
        preview,
    ):
        if preview:
            return "#"

        token = (
            self.token_service
            .generate_for_recipient(
                campaign=campaign,
                recipient=recipient,
                action=action,
            )
        )

        if action == ACTION_UNSUBSCRIBE:
            return (
                self.url_builder
                .unsubscribe(token)
            )

        return (
            self.url_builder
            .resubscribe(token)
        )