# apps/communication/services/suppression.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.db.models import Q

from apps.communication.constants import (
    EmailSubscriptionStatus,
    RE_ENGAGEMENT,
)
from apps.communication.models import (
    EmailSubscriptionPreference,
    UnsubscribedUser,
)


class EmailSuppressionService:
    """
    Apply campaign unsubscribe and suppression rules.
    """

    def get_reason(self, campaign, recipient):
        if campaign.ignore_unsubscribe:
            return None

        # Preserve the existing legacy re-engagement behavior.
        if campaign.target_group == RE_ENGAGEMENT:
            return None

        if (
            campaign.audience_id
            and not campaign.audience.respect_unsubscribe
        ):
            return None

        if (
            recipient.external_contact
            and recipient.external_contact.is_unsubscribed
        ):
            return "external_contact_unsubscribed"

        global_query = Q(
            email__iexact=recipient.email
        )

        if recipient.user_id:
            global_query |= Q(
                user_id=recipient.user_id
            )

        if UnsubscribedUser.objects.filter(
            global_query
        ).exists():
            return "global_unsubscribe"

        if campaign.topic_id:
            if EmailSubscriptionPreference.objects.filter(
                email__iexact=recipient.email,
                topic_id=campaign.topic_id,
                status=EmailSubscriptionStatus.UNSUBSCRIBED,
            ).exists():
                return "topic_unsubscribe"

        return None