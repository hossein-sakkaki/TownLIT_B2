# apps/organizations/urls.py
#
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-05.
#

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.organizations.views import (
    OrganizationAdministrationOverviewView,
    OrganizationAuditActivityView,
    OrganizationBootstrapView,
    OrganizationCommunityPeopleView,
    OrganizationDiscoveryView,
    OrganizationGovernanceProposalCancelView,
    OrganizationGovernanceProposalDetailView,
    OrganizationGovernanceProposalFinalizeView,
    OrganizationGovernanceProposalOpenView,
    OrganizationGovernanceOwnerCandidatesView,
    OrganizationGovernanceProposalsView,
    OrganizationGovernanceProposalVoteView,
    OrganizationGovernanceRulesView,
    OrganizationMemberCandidatesView,
    OrganizationMembersView,
    OrganizationMembershipRequestsManagementView,
    OrganizationMembershipRequestViewSet,
    OrganizationMembershipViewSet,
    OrganizationModuleActivateView,
    OrganizationModuleCatalogView,
    OrganizationModuleDetailView,
    OrganizationModuleDisableView,
    OrganizationModuleRestoreView,
    OrganizationModulesView,
    OrganizationModuleSuspendView,
    OrganizationPlatformBootstrapView,
    OrganizationRelationshipCandidatesView,
    OrganizationRelationshipConsentProposalView,
    OrganizationRelationshipDetailView,
    OrganizationRelationshipRequestView,
    OrganizationRelationshipsView,
    OrganizationRoleAssignmentsManagementView,
    OrganizationRolesView,
    OrganizationRoleAssignmentViewSet,
    OrganizationVerificationApproveView,
    OrganizationVerificationCaseDetailView,
    OrganizationVerificationCasesView,
    OrganizationVerificationDocumentCreateView,
    OrganizationVerificationDocumentDetailView,
    OrganizationVerificationDocumentReviewView,
    OrganizationVerificationGrantRevokeView,
    OrganizationVerificationNeedsInformationView,
    OrganizationVerificationRejectView,
    OrganizationVerificationReviewQueueView,
    OrganizationVerificationStartReviewView,
    OrganizationVerificationSubmitView,
    OrganizationVerificationSponsorRelationshipsView,
    OrganizationVerificationWithdrawView,
    OrganizationViewSet,
    OrganizationBusinessHoursView,
    OrganizationContactPointDetailView,
    OrganizationContactPointsView,
    OrganizationRepresentativeCandidatesView,
    OrganizationRepresentativeDetailView,
    OrganizationRepresentativeResponseView,
    OrganizationRepresentativesView,
    OrganizationSocialLinkDetailView,
    OrganizationSocialLinksView,
)
from apps.organizations.views.profile import OrganizationSocialMediaTypesView


router = DefaultRouter()
router.register(
    r"membership-requests",
    OrganizationMembershipRequestViewSet,
    basename="organization-membership-request",
)
router.register(
    r"memberships",
    OrganizationMembershipViewSet,
    basename="organization-membership",
)
router.register(
    r"role-assignments",
    OrganizationRoleAssignmentViewSet,
    basename="organization-role-assignment",
)
router.register(
    r"",
    OrganizationViewSet,
    basename="organization",
)


urlpatterns = [
    # Stable client bootstrap contract.
    path(
        "system/bootstrap/",
        OrganizationPlatformBootstrapView.as_view(),
        name="organization-platform-bootstrap",
    ),
    path(
        "system/module-catalog/",
        OrganizationModuleCatalogView.as_view(),
        name="organization-module-catalog",
    ),
    path(
        "discovery/",
        OrganizationDiscoveryView.as_view(),
        name="organization-discovery",
    ),
    path(
        "<slug:slug>/bootstrap/",
        OrganizationBootstrapView.as_view(),
        name="organization-bootstrap",
    ),

    # Public-safe Community relationship lists.
    path(
        "<slug:slug>/profile/community/",
        OrganizationCommunityPeopleView.as_view(),
        name="organization-community-people",
    ),

    # Administration.
    path(
        "<slug:slug>/administration/overview/",
        OrganizationAdministrationOverviewView.as_view(),
        name="organization-administration-overview",
    ),
    path(
        "<slug:slug>/administration/activity/",
        OrganizationAuditActivityView.as_view(),
        name="organization-administration-activity",
    ),

    # People & Access.
    path(
        "<slug:slug>/people/member-candidates/",
        OrganizationMemberCandidatesView.as_view({
            "get": "list",
        }),
        name="organization-member-candidates",
    ),
    path(
        "<slug:slug>/people/memberships/",
        OrganizationMembersView.as_view({
            "get": "list",
        }),
        name="organization-people-memberships",
    ),
    path(
        "<slug:slug>/people/membership-requests/",
        OrganizationMembershipRequestsManagementView.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization-people-membership-requests",
    ),
    path(
        "<slug:slug>/people/roles/",
        OrganizationRolesView.as_view({
            "get": "list",
        }),
        name="organization-people-roles",
    ),
    path(
        "<slug:slug>/people/role-assignments/",
        OrganizationRoleAssignmentsManagementView.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization-people-role-assignments",
    ),

    # Organization modules.
    path(
        "<slug:slug>/modules/",
        OrganizationModulesView.as_view(),
        name="organization-modules",
    ),
    path(
        "<slug:slug>/modules/<slug:module_key>/",
        OrganizationModuleDetailView.as_view(),
        name="organization-module-detail",
    ),
    path(
        "<slug:slug>/modules/<slug:module_key>/activate/",
        OrganizationModuleActivateView.as_view(),
        name="organization-module-activate",
    ),
    path(
        "<slug:slug>/modules/<slug:module_key>/disable/",
        OrganizationModuleDisableView.as_view(),
        name="organization-module-disable",
    ),
    path(
        "<slug:slug>/modules/<slug:module_key>/suspend/",
        OrganizationModuleSuspendView.as_view(),
        name="organization-module-suspend",
    ),
    path(
        "<slug:slug>/modules/<slug:module_key>/restore/",
        OrganizationModuleRestoreView.as_view(),
        name="organization-module-restore",
    ),

    # Verification owner/admin workflows.
    path(
        "<slug:slug>/verification/cases/",
        OrganizationVerificationCasesView.as_view(),
        name="organization-verification-cases",
    ),
    path(
        "<slug:slug>/verification/sponsor-relationships/",
        OrganizationVerificationSponsorRelationshipsView.as_view(),
        name="organization-verification-sponsor-relationships",
    ),
    path(
        "workflow/verification/review-queue/",
        OrganizationVerificationReviewQueueView.as_view(),
        name="organization-verification-review-queue",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/",
        OrganizationVerificationCaseDetailView.as_view(),
        name="organization-verification-case-detail",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/documents/",
        OrganizationVerificationDocumentCreateView.as_view(),
        name="organization-verification-document-create",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/submit/",
        OrganizationVerificationSubmitView.as_view(),
        name="organization-verification-submit",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/withdraw/",
        OrganizationVerificationWithdrawView.as_view(),
        name="organization-verification-withdraw",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/start-review/",
        OrganizationVerificationStartReviewView.as_view(),
        name="organization-verification-start-review",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/needs-information/",
        OrganizationVerificationNeedsInformationView.as_view(),
        name="organization-verification-needs-information",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/approve/",
        OrganizationVerificationApproveView.as_view(),
        name="organization-verification-approve",
    ),
    path(
        "workflow/verification/cases/<uuid:public_id>/reject/",
        OrganizationVerificationRejectView.as_view(),
        name="organization-verification-reject",
    ),
    path(
        "workflow/verification/documents/<uuid:public_id>/",
        OrganizationVerificationDocumentDetailView.as_view(),
        name="organization-verification-document-detail",
    ),
    path(
        "workflow/verification/documents/<uuid:public_id>/review/",
        OrganizationVerificationDocumentReviewView.as_view(),
        name="organization-verification-document-review",
    ),
    path(
        "workflow/verification/grants/<uuid:public_id>/revoke/",
        OrganizationVerificationGrantRevokeView.as_view(),
        name="organization-verification-grant-revoke",
    ),

    # Hierarchy and relationships.
    path(
        "<slug:slug>/relationships/candidates/",
        OrganizationRelationshipCandidatesView.as_view(),
        name="organization-relationship-candidates",
    ),
    path(
        "<slug:slug>/relationships/",
        OrganizationRelationshipsView.as_view(),
        name="organization-relationships",
    ),
    path(
        "workflow/relationships/request/",
        OrganizationRelationshipRequestView.as_view(),
        name="organization-relationship-request",
    ),
    path(
        "workflow/relationships/<uuid:public_id>/",
        OrganizationRelationshipDetailView.as_view(),
        name="organization-relationship-detail",
    ),
    path(
        "workflow/relationships/<uuid:public_id>/consent-proposal/",
        OrganizationRelationshipConsentProposalView.as_view(),
        name="organization-relationship-consent-proposal",
    ),

    # Governance.
    path(
        "<slug:slug>/governance/rules/",
        OrganizationGovernanceRulesView.as_view(),
        name="organization-governance-rules",
    ),
    path(
        "<slug:slug>/governance/owner-candidates/",
        OrganizationGovernanceOwnerCandidatesView.as_view(),
        name="organization-governance-owner-candidates",
    ),
    path(
        "<slug:slug>/governance/proposals/",
        OrganizationGovernanceProposalsView.as_view(),
        name="organization-governance-proposals",
    ),
    path(
        "workflow/governance/proposals/<uuid:public_id>/",
        OrganizationGovernanceProposalDetailView.as_view(),
        name="organization-governance-proposal-detail",
    ),
    path(
        "workflow/governance/proposals/<uuid:public_id>/open/",
        OrganizationGovernanceProposalOpenView.as_view(),
        name="organization-governance-proposal-open",
    ),
    path(
        "workflow/governance/proposals/<uuid:public_id>/vote/",
        OrganizationGovernanceProposalVoteView.as_view(),
        name="organization-governance-proposal-vote",
    ),
    path(
        "workflow/governance/proposals/<uuid:public_id>/finalize/",
        OrganizationGovernanceProposalFinalizeView.as_view(),
        name="organization-governance-proposal-finalize",
    ),
    path(
        "workflow/governance/proposals/<uuid:public_id>/cancel/",
        OrganizationGovernanceProposalCancelView.as_view(),
        name="organization-governance-proposal-cancel",
    ),

    # Church.
    path(
        "<slug:slug>/modules/church/",
        include("apps.organizations.modules.church.urls"),
    ),

    # Worship.
    path(
        "<slug:slug>/modules/worship/",
        include("apps.organizations.modules.worship.urls"),
    ),
    
    # Organization profile.
    path(
        "<slug:slug>/profile/contacts/",
        OrganizationContactPointsView.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization-profile-contacts",
    ),
    path(
        "<slug:slug>/profile/contacts/<uuid:public_id>/",
        OrganizationContactPointDetailView.as_view({
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="organization-profile-contact-detail",
    ),
    path(
        "<slug:slug>/profile/business-hours/",
        OrganizationBusinessHoursView.as_view({
            "get": "list",
            "put": "replace",
        }),
        name="organization-business-hours",
    ),
    path(
        "<slug:slug>/profile/representative-candidates/",
        OrganizationRepresentativeCandidatesView.as_view({
            "get": "list",
        }),
        name="organization-representative-candidates",
    ),
    path(
        "<slug:slug>/profile/representatives/",
        OrganizationRepresentativesView.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization-representatives",
    ),
    path(
        "<slug:slug>/profile/representatives/<uuid:public_id>/",
        OrganizationRepresentativeDetailView.as_view({
            "delete": "destroy",
        }),
        name="organization-representative-detail",
    ),
    path(
        "<slug:slug>/profile/representatives/<uuid:public_id>/respond/",
        OrganizationRepresentativeResponseView.as_view({
            "post": "respond",
        }),
        name="organization-representative-response",
    ),
    path(
        "<slug:slug>/profile/social-links/",
        OrganizationSocialLinksView.as_view({
            "get": "list",
            "post": "create",
        }),
        name="organization-social-links",
    ),
    path(
        "<slug:slug>/profile/social-links/<int:link_id>/",
        OrganizationSocialLinkDetailView.as_view({
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="organization-social-link-detail",
    ),
    path(
        "<slug:slug>/profile/social-media-types/",
        OrganizationSocialMediaTypesView.as_view({
            "get": "list",
        }),
        name="organization-social-media-types",
    ),
    
] + router.urls
