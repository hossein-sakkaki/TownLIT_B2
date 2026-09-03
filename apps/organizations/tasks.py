# apps/organizations/tasks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from celery import shared_task
from django.utils import timezone

from apps.organizations.constants import (
    MembershipRequestStatus,
    OrganizationGovernanceProposalStatus,
)
from apps.organizations.feature_flags import organization_governance_enabled
from apps.organizations.models import (
    OrganizationGovernanceProposal,
    OrganizationMembershipRequest,
)
from apps.organizations.services.governance import finalize_governance_proposal
from apps.organizations.services.verification import expire_due_verification_grants


@shared_task
def expire_organization_membership_requests():
    now = timezone.now()

    return (
        OrganizationMembershipRequest.objects
        .filter(
            status=MembershipRequestStatus.PENDING,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .update(
            status=MembershipRequestStatus.EXPIRED,
            pending_slot=None,
            responded_at=now,
            updated_at=now,
        )
    )


@shared_task
def expire_organization_verification_grants():
    return expire_due_verification_grants()


@shared_task
def finalize_due_organization_governance_proposals():
    if not organization_governance_enabled():
        return 0

    now = timezone.now()
    proposal_ids = list(
        OrganizationGovernanceProposal.objects
        .filter(
            status=OrganizationGovernanceProposalStatus.OPEN,
            closes_at__isnull=False,
            closes_at__lte=now,
        )
        .values_list("id", flat=True)
    )

    finalized = 0

    for proposal_id in proposal_ids:
        proposal = OrganizationGovernanceProposal.objects.filter(
            pk=proposal_id,
            status=OrganizationGovernanceProposalStatus.OPEN,
        ).first()

        if not proposal:
            continue

        finalize_governance_proposal(
            proposal=proposal,
            actor=None,
            now=now,
            allow_early_if_all_voted=False,
        )
        finalized += 1

    return finalized
