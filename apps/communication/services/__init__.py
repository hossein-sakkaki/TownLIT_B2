# apps/communication/services/__init__.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from .analytics import EmailAnalyticsService
from .campaign_delivery import (
    CampaignDeliveryService,
    CampaignSendResult,
    send_campaign_email_batch,
    send_test_email_for_campaign,
)
from .external_campaigns import send_external_email_campaign
from .legacy_targets import get_users_for_campaign
from .preferences import (
    EmailPreferenceService,
    PreferenceActionResult,
)
from .recipients import AudienceResolver, EmailRecipient
from .rendering import (
    CampaignRenderer,
    EmailTemplateRenderer,
    RenderedCampaignEmail,
    RenderedTemplateEmail,
)
from .scheduling import (
    CampaignQueueResult,
    CampaignSchedulingService,
)
from .suppression import EmailSuppressionService
from .tracking import EmailTrackingService
from .review import (
    CampaignPreflightCheck,
    CampaignPreflightReport,
    CampaignPreflightService,
    CampaignSuppressionSummary,
)

__all__ = [
    "AudienceResolver",
    "CampaignDeliveryService",
    "CampaignQueueResult",
    "CampaignRenderer",
    "CampaignSchedulingService",
    "CampaignSendResult",
    "EmailAnalyticsService",
    "EmailPreferenceService",
    "EmailRecipient",
    "EmailSuppressionService",
    "EmailTemplateRenderer",
    "EmailTrackingService",
    "PreferenceActionResult",
    "RenderedCampaignEmail",
    "RenderedTemplateEmail",
    "get_users_for_campaign",
    "send_campaign_email_batch",
    "send_external_email_campaign",
    "send_test_email_for_campaign",
    
    "CampaignPreflightCheck",
    "CampaignPreflightReport",
    "CampaignPreflightService",
    "CampaignSuppressionSummary",
]