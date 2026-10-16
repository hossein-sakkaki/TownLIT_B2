# apps/conversation/constants/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.db import models


class OrganizationConversationContextType(models.TextChoices):
    DIRECT = "direct", "Organization Direct"
    MEMBERS_COMMUNITY = "members_community", "Members Community"


class OrganizationConversationStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class OrganizationConversationWaitingFor(models.TextChoices):
    NONE = "none", "None"
    ORGANIZATION = "organization", "Organization"
    PARTICIPANT = "participant", "Participant"
