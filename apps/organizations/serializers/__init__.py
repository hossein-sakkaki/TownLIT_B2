# apps/organizations/serializers/__init__.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from .administration import (
    OrganizationAdministrationOverviewSerializer,
    OrganizationAuditLogSerializer,
)
from .organization import (
    OrganizationListSerializer,
    OrganizationReferenceSerializer,
    OrganizationSerializer,
    OrganizationWriteSerializer,
)
from .membership import (
    OrganizationMembershipRequestSerializer,
    OrganizationMembershipSerializer,
)
from .role import (
    OrganizationRoleAssignmentSerializer,
    OrganizationRoleSerializer,
)
from .bootstrap import (
    OrganizationClientFeatureFlagsSerializer,
    OrganizationCreationEligibilitySerializer,
    OrganizationFeatureFlagsSerializer,
)
from .modules import (
    OrganizationModuleAccessSerializer,
    OrganizationModuleActivationSerializer,
    OrganizationModuleActivationWriteSerializer,
    OrganizationModuleDefinitionSerializer,
    OrganizationModuleSuspensionSerializer,
)
from .verification import (
    OrganizationVerificationApprovalSerializer,
    OrganizationVerificationCaseCreateSerializer,
    OrganizationVerificationCaseSerializer,
    OrganizationVerificationCaseUpdateSerializer,
    OrganizationVerificationDocumentCreateSerializer,
    OrganizationVerificationDocumentReviewSerializer,
    OrganizationVerificationDocumentSerializer,
    OrganizationVerificationGrantSerializer,
    OrganizationVerificationReviewNoteSerializer,
    OrganizationVerificationRevokeSerializer,
)
from .hierarchy import (
    OrganizationRelationshipCandidateSerializer,
    OrganizationRelationshipConsentProposalSerializer,
    OrganizationRelationshipConsentSerializer,
    OrganizationRelationshipCreateSerializer,
    OrganizationRelationshipSerializer,
)
from .governance import (
    OrganizationGovernanceDecisionSerializer,
    OrganizationGovernanceProposalCreateSerializer,
    OrganizationGovernanceProposalSerializer,
    OrganizationGovernanceRuleSerializer,
    OrganizationGovernanceVoteSerializer,
)
from .people import (
    OrganizationMemberCandidateSerializer,
    OrganizationMembershipInvitationCreateSerializer,
    OrganizationMembershipManagementSerializer,
    OrganizationRoleAssignmentCreateSerializer,
    OrganizationRoleAssignmentManagementSerializer,
)
from .profile import (
    OrganizationBusinessHourSerializer,
    OrganizationContactPointSerializer,
    OrganizationRepresentativeCandidateSerializer,
    OrganizationRepresentativeCreateSerializer,
    OrganizationRepresentativeResponseSerializer,
    OrganizationRepresentativeSerializer,
    OrganizationSocialLinkSerializer,
    OrganizationSocialLinkWriteSerializer,
    OrganizationSocialMediaTypeSerializer,
)


__all__ = [
    # Administration
    "OrganizationAdministrationOverviewSerializer",
    "OrganizationAuditLogSerializer",

    # Organization
    "OrganizationListSerializer",
    "OrganizationReferenceSerializer",
    "OrganizationSerializer",
    "OrganizationWriteSerializer",

    # Profile extensions
    "OrganizationBusinessHourSerializer",
    "OrganizationContactPointSerializer",
    "OrganizationRepresentativeCandidateSerializer",
    "OrganizationRepresentativeCreateSerializer",
    "OrganizationRepresentativeResponseSerializer",
    "OrganizationRepresentativeSerializer",
    "OrganizationSocialLinkSerializer",
    "OrganizationSocialLinkWriteSerializer",
    "OrganizationSocialMediaTypeSerializer",

    # People & Access
    "OrganizationMemberCandidateSerializer",
    "OrganizationMembershipInvitationCreateSerializer",
    "OrganizationMembershipManagementSerializer",
    "OrganizationRoleAssignmentCreateSerializer",
    "OrganizationRoleAssignmentManagementSerializer",

    # Membership
    "OrganizationMembershipRequestSerializer",
    "OrganizationMembershipSerializer",

    # Roles
    "OrganizationRoleAssignmentSerializer",
    "OrganizationRoleSerializer",

    # Bootstrap
    "OrganizationClientFeatureFlagsSerializer",
    "OrganizationCreationEligibilitySerializer",
    "OrganizationFeatureFlagsSerializer",

    # Modules
    "OrganizationModuleAccessSerializer",
    "OrganizationModuleActivationSerializer",
    "OrganizationModuleActivationWriteSerializer",
    "OrganizationModuleDefinitionSerializer",
    "OrganizationModuleSuspensionSerializer",

    # Verification
    "OrganizationVerificationApprovalSerializer",
    "OrganizationVerificationCaseCreateSerializer",
    "OrganizationVerificationCaseSerializer",
    "OrganizationVerificationCaseUpdateSerializer",
    "OrganizationVerificationDocumentCreateSerializer",
    "OrganizationVerificationDocumentReviewSerializer",
    "OrganizationVerificationDocumentSerializer",
    "OrganizationVerificationGrantSerializer",
    "OrganizationVerificationReviewNoteSerializer",
    "OrganizationVerificationRevokeSerializer",

    # Hierarchy
    "OrganizationRelationshipCandidateSerializer",
    "OrganizationRelationshipConsentProposalSerializer",
    "OrganizationRelationshipConsentSerializer",
    "OrganizationRelationshipCreateSerializer",
    "OrganizationRelationshipSerializer",

    # Governance
    "OrganizationGovernanceDecisionSerializer",
    "OrganizationGovernanceProposalCreateSerializer",
    "OrganizationGovernanceProposalSerializer",
    "OrganizationGovernanceRuleSerializer",
    "OrganizationGovernanceVoteSerializer",
]

from .discovery import (
    OrganizationDiscoveryQuerySerializer,
    OrganizationDiscoveryResultSerializer,
)
