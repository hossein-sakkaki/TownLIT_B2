# apps/organizations/models/__init__.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from .organization import Organization
from .connection import OrganizationConnection
from .membership import (
    OrganizationMembership,
    OrganizationMembershipRequest,
)
from .role import (
    OrganizationPermission,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRolePermission,
)
from .verification import (
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
    OrganizationVerificationGrant,
)
from .hierarchy import (
    OrganizationRelationship,
    OrganizationRelationshipConsent,
)
from .governance import (
    OrganizationGovernanceDecision,
    OrganizationGovernanceElector,
    OrganizationGovernanceProposal,
    OrganizationGovernanceRule,
    OrganizationGovernanceVote,
    OrganizationGovernanceVoteRevision,
)
from .module import (
    OrganizationModuleActivation,
    OrganizationModuleDefinition,
)
from .audit import OrganizationAuditLog

# Specialized Organization module models are registered through this app.
from apps.organizations.modules.church.models import (
    ChurchAttendanceRecord,
    ChurchAttendanceSession,
    ChurchAuditLog,
    ChurchCampus,
    ChurchGatheringOccurrence,
    ChurchGatheringSeries,
    ChurchLeadershipAssignment,
    ChurchMinistry,
    ChurchMinistryMembership,
    ChurchWorkspace,
    ChurchServingTeam,
    ChurchServingTeamMembership,
    ChurchServicePlan,
    ChurchServicePlanItem,
    ChurchServingAssignment,
    ChurchResource,
    ChurchResourceReservation,
    ChurchCongregant,
    ChurchHousehold,
    ChurchHouseholdMembership,
    ChurchPastoralCareCase,
    ChurchPastoralCareAssignment,
    ChurchPastoralCareNote,
    ChurchPastoralCareContact,
    ChurchTeachingSeries,
)

__all__ = [
    "Organization",
    "OrganizationConnection",
    "OrganizationMembership",
    "OrganizationMembershipRequest",
    "OrganizationPermission",
    "OrganizationRole",
    "OrganizationRoleAssignment",
    "OrganizationRolePermission",
    "OrganizationVerificationCase",
    "OrganizationVerificationDocument",
    "OrganizationVerificationGrant",
    "OrganizationRelationship",
    "OrganizationRelationshipConsent",
    "OrganizationGovernanceDecision",
    "OrganizationGovernanceElector",
    "OrganizationGovernanceProposal",
    "OrganizationGovernanceRule",
    "OrganizationGovernanceVote",
    "OrganizationGovernanceVoteRevision",
    "OrganizationModuleActivation",
    "OrganizationModuleDefinition",
    "OrganizationAuditLog",
    "ChurchWorkspace",
    "ChurchCampus",
    "ChurchMinistry",
    "ChurchMinistryMembership",
    "ChurchLeadershipAssignment",
    "ChurchGatheringSeries",
    "ChurchGatheringOccurrence",
    "ChurchAttendanceSession",
    "ChurchAttendanceRecord",
    "ChurchAuditLog",
    "ChurchServingTeam",
    "ChurchServingTeamMembership",
    "ChurchServicePlan",
    "ChurchServicePlanItem",
    "ChurchServingAssignment",
    "ChurchResource",
    "ChurchResourceReservation",
    "ChurchCongregant",
    "ChurchHousehold",
    "ChurchHouseholdMembership",
    "ChurchPastoralCareCase",
    "ChurchPastoralCareAssignment",
    "ChurchPastoralCareNote",
    "ChurchPastoralCareContact",
    "ChurchTeachingSeries",
]


from apps.organizations.modules.worship.models import (
    WorshipWorkspace,
    OrganizationRightsParty,
    OrganizationMusicLicense,
    OrganizationMusicLicenseEvidence,
    OrganizationMusicContribution,
    WorshipAuditLog,
)

__all__ += [
    "WorshipWorkspace",
    "OrganizationRightsParty",
    "OrganizationMusicLicense",
    "OrganizationMusicLicenseEvidence",
    "OrganizationMusicContribution",
    "WorshipAuditLog",
]
