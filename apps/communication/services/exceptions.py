# apps/communication/services/exceptions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


class CommunicationServiceError(Exception):
    """Base communication service error."""


class AudienceConfigurationError(CommunicationServiceError):
    """Raised when an audience rule cannot be resolved safely."""


class CampaignStateError(CommunicationServiceError):
    """Raised when a campaign operation is not allowed."""


class CampaignRenderError(CommunicationServiceError):
    """Raised when campaign content cannot be rendered."""