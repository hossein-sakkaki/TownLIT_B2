# apps/organizations/urls.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-09-08.
#

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.organizations.views import (
    OrganizationBootstrapView,
    OrganizationGovernanceProposalCancelView,
    OrganizationGovernanceProposalDetailView,
    OrganizationGovernanceProposalFinalizeView,
    OrganizationGovernanceProposalOpenView,
    OrganizationGovernanceProposalsView,
    OrganizationGovernanceProposalVoteView,
    OrganizationGovernanceRulesView,
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
    OrganizationRelationshipConsentProposalView,
    OrganizationRelationshipDetailView,
    OrganizationRelationshipRequestView,
    OrganizationRelationshipsView,
    OrganizationRoleAssignmentViewSet,
    OrganizationVerificationApproveView,
    OrganizationVerificationCaseDetailView,
    OrganizationVerificationCasesView,
    OrganizationVerificationDocumentCreateView,
    OrganizationVerificationDocumentReviewView,
    OrganizationVerificationGrantRevokeView,
    OrganizationVerificationNeedsInformationView,
    OrganizationVerificationRejectView,
    OrganizationVerificationReviewQueueView,
    OrganizationVerificationStartReviewView,
    OrganizationVerificationSubmitView,
    OrganizationVerificationWithdrawView,
    OrganizationViewSet,
)


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
        "<slug:slug>/bootstrap/",
        OrganizationBootstrapView.as_view(),
        name="organization-bootstrap",
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
] + router.urls
