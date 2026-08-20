# apps/communication/models/__init__.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from .design import EmailTheme

from .templates import (
    EmailTemplate,
    EmailTemplateBlock,
)

from .legacy import (
    DraftCampaign,
    ScheduledEmail,
    ExternalEmailCampaign,
    ExternalContact,
)

from .audiences import (
    EmailAudience,
    EmailAudienceRule,
)

from .subscriptions import (
    EmailTopic,
    EmailSubscriptionPreference,
    UnsubscribedUser,
)

from .campaigns import (
    EmailCampaign,
    EmailCampaignBlock,
)

from .delivery import (
    EmailLog,
    EmailEvent,
    EmailCampaignDailyMetric,
)


__all__ = [
    "EmailTheme",
    "EmailTemplate",
    "EmailTemplateBlock",
    "EmailAudience",
    "EmailAudienceRule",
    "EmailTopic",
    "EmailSubscriptionPreference",
    "UnsubscribedUser",
    "EmailCampaign",
    "EmailCampaignBlock",
    "EmailLog",
    "EmailEvent",
    "EmailCampaignDailyMetric",
    "DraftCampaign",
    "ScheduledEmail",
    "ExternalEmailCampaign",
    "ExternalContact",
]