# apps/organizations/services/hierarchy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.organizations.constants import (
    CURRENT_RELATIONSHIP_STATUSES,
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationGovernanceAction,
    OrganizationGovernanceProposalStatus,
    OrganizationPermissionKey,
    OrganizationRelationshipConsentStatus,
    OrganizationRelationshipStatus,
    OrganizationRelationshipType,
    OrganizationVerificationGrantStatus,
)
from apps.organizations.feature_flags import ensure_organization_hierarchy_enabled
from apps.organizations.models import (
    OrganizationAuditLog,
    OrganizationRelationship,
    OrganizationRelationshipConsent,
    OrganizationVerificationGrant,
)
from apps.organizations.services.access import user_has_organization_permission


HIERARCHICAL_RELATIONSHIP_TYPES = {
    OrganizationRelationshipType.PARENT_BRANCH,
    OrganizationRelationshipType.SPONSORSHIP,
}


def _ensure_relationship_manager(*, organization, actor):
    if getattr(actor, "is_staff", False):
        return

    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_GOVERNANCE,
    ):
        raise PermissionDenied(
            "You do not have permission to manage organization relationships."
        )


def _would_create_relationship_cycle(
    *,
    source_organization,
    target_organization,
    relationship_type,
):
    if relationship_type not in HIERARCHICAL_RELATIONSHIP_TYPES:
        return False

    frontier = [target_organization.id]
    visited = set()

    while frontier:
        organization_id = frontier.pop()

        if organization_id == source_organization.id:
            return True

        if organization_id in visited:
            continue

        visited.add(organization_id)

        child_ids = (
            OrganizationRelationship.objects
            .filter(
                source_organization_id=organization_id,
                relationship_type__in=HIERARCHICAL_RELATIONSHIP_TYPES,
                status__in=CURRENT_RELATIONSHIP_STATUSES,
            )
            .values_list("target_organization_id", flat=True)
        )

        frontier.extend(child_ids)

    return False


@transaction.atomic
def request_organization_relationship(
    *,
    source_organization,
    target_organization,
    relationship_type,
    actor,
    requested_by_organization,
    metadata=None,
):
    ensure_organization_hierarchy_enabled()

    if requested_by_organization.id not in {
        source_organization.id,
        target_organization.id,
    }:
        raise ValidationError(
            "The requesting organization must be a relationship party."
        )

    _ensure_relationship_manager(
        organization=requested_by_organization,
        actor=actor,
    )

    if source_organization.id == target_organization.id:
        raise ValidationError(
            "An organization cannot create a relationship with itself."
        )

    if _would_create_relationship_cycle(
        source_organization=source_organization,
        target_organization=target_organization,
        relationship_type=relationship_type,
    ):
        raise ValidationError(
            "This relationship would create an organization hierarchy cycle."
        )

    relationship = OrganizationRelationship(
        source_organization=source_organization,
        target_organization=target_organization,
        relationship_type=relationship_type,
        status=OrganizationRelationshipStatus.PENDING,
        requested_by_organization=requested_by_organization,
        requested_by=actor,
        metadata=metadata or {},
    )
    relationship.full_clean()

    try:
        with transaction.atomic():
            relationship.save()
    except IntegrityError as exc:
        raise ValidationError(
            "A current relationship of this type already exists or conflicts "
            "with the target organization's current authority."
        ) from exc

    for organization in (
        source_organization,
        target_organization,
    ):
        OrganizationRelationshipConsent.objects.create(
            relationship=relationship,
            organization=organization,
            status=OrganizationRelationshipConsentStatus.PENDING,
        )

    for organization in (
        source_organization,
        target_organization,
    ):
        OrganizationAuditLog.objects.create(
            organization=organization,
            action=OrganizationAuditAction.RELATIONSHIP_REQUESTED,
            source=OrganizationAuditSource.SERVICE,
            actor=actor,
            relationship=relationship,
            metadata={
                "relationship_id": relationship.id,
                "relationship_public_id": str(relationship.public_id),
                "relationship_type": relationship.relationship_type,
                "source_organization_id": source_organization.id,
                "target_organization_id": target_organization.id,
                "requested_by_organization_id": requested_by_organization.id,
            },
        )

    return relationship


@transaction.atomic
def create_relationship_consent_proposal(
    *,
    relationship,
    organization,
    actor,
):
    ensure_organization_hierarchy_enabled()

    relationship = (
        OrganizationRelationship.objects
        .select_for_update()
        .select_related(
            "source_organization",
            "target_organization",
        )
        .get(pk=relationship.pk)
    )

    if relationship.status != OrganizationRelationshipStatus.PENDING:
        raise ValidationError(
            "Only pending relationships can request governance consent."
        )

    if organization.id not in {
        relationship.source_organization_id,
        relationship.target_organization_id,
    }:
        raise ValidationError(
            "Organization is not a relationship party."
        )

    _ensure_relationship_manager(
        organization=organization,
        actor=actor,
    )

    consent = (
        OrganizationRelationshipConsent.objects
        .select_for_update()
        .get(
            relationship=relationship,
            organization=organization,
        )
    )

    if consent.status == OrganizationRelationshipConsentStatus.APPROVED:
        return consent.governance_proposal

    if consent.status != OrganizationRelationshipConsentStatus.PENDING:
        raise ValidationError(
            "This relationship consent is no longer pending."
        )

    if (
        consent.governance_proposal_id
        and consent.governance_proposal.status
        in {
            OrganizationGovernanceProposalStatus.DRAFT,
            OrganizationGovernanceProposalStatus.OPEN,
        }
    ):
        return consent.governance_proposal

    from apps.organizations.services.governance import (
        create_governance_proposal,
    )

    proposal = create_governance_proposal(
        organization=organization,
        action_key=OrganizationGovernanceAction.RELATIONSHIP_CONSENT,
        title=(
            f"Approve {relationship.get_relationship_type_display()} "
            "relationship"
        ),
        actor=actor,
        relationship=relationship,
        payload={
            "relationship_id": relationship.id,
            "relationship_public_id": str(relationship.public_id),
        },
    )

    consent.governance_proposal = proposal
    consent.save(
        update_fields=[
            "governance_proposal",
            "updated_at",
        ]
    )

    return proposal


@transaction.atomic
def apply_relationship_consent_decision_from_governance(
    *,
    relationship,
    organization,
    approved,
    actor=None,
    note=None,
    now=None,
):
    ensure_organization_hierarchy_enabled()
    now = now or timezone.now()

    relationship = (
        OrganizationRelationship.objects
        .select_for_update()
        .select_related(
            "source_organization",
            "target_organization",
        )
        .get(pk=relationship.pk)
    )

    if relationship.status != OrganizationRelationshipStatus.PENDING:
        raise ValidationError(
            "Relationship consent can only be decided while pending."
        )

    consent = (
        OrganizationRelationshipConsent.objects
        .select_for_update()
        .get(
            relationship=relationship,
            organization=organization,
        )
    )

    if consent.status != OrganizationRelationshipConsentStatus.PENDING:
        return consent

    consent.status = (
        OrganizationRelationshipConsentStatus.APPROVED
        if approved
        else OrganizationRelationshipConsentStatus.REJECTED
    )
    consent.decided_by = actor
    consent.decided_at = now
    consent.note = note
    consent.save(
        update_fields=[
            "status",
            "decided_by",
            "decided_at",
            "note",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=(
            OrganizationAuditAction.RELATIONSHIP_CONSENT_APPROVED
            if approved
            else OrganizationAuditAction.RELATIONSHIP_CONSENT_REJECTED
        ),
        source=OrganizationAuditSource.GOVERNANCE,
        actor=actor,
        relationship=relationship,
        metadata={
            "relationship_id": relationship.id,
            "approved": approved,
            "note": note,
        },
    )

    if not approved:
        relationship.status = OrganizationRelationshipStatus.REJECTED
        relationship.end_reason = note
        relationship.save(
            update_fields=[
                "status",
                "end_reason",
                "updated_at",
            ]
        )

        relationship.consents.filter(
            status=OrganizationRelationshipConsentStatus.PENDING,
        ).exclude(pk=consent.pk).update(
            status=OrganizationRelationshipConsentStatus.REVOKED,
            decided_at=now,
            updated_at=now,
        )

        return consent

    activate_relationship_if_ready(
        relationship=relationship,
        actor=actor,
        now=now,
    )

    return consent


@transaction.atomic
def activate_relationship_if_ready(
    *,
    relationship,
    actor=None,
    now=None,
):
    now = now or timezone.now()

    relationship = (
        OrganizationRelationship.objects
        .select_for_update()
        .select_related(
            "source_organization",
            "target_organization",
        )
        .get(pk=relationship.pk)
    )

    if relationship.status != OrganizationRelationshipStatus.PENDING:
        return relationship

    consents = list(
        relationship.consents.select_for_update().all()
    )

    if len(consents) != 2:
        raise ValidationError(
            "Relationship requires consent records for both parties."
        )

    if not all(
        consent.status
        == OrganizationRelationshipConsentStatus.APPROVED
        for consent in consents
    ):
        return relationship

    if _would_create_relationship_cycle(
        source_organization=relationship.source_organization,
        target_organization=relationship.target_organization,
        relationship_type=relationship.relationship_type,
    ):
        raise ValidationError(
            "Activating this relationship would create a hierarchy cycle."
        )

    relationship.status = OrganizationRelationshipStatus.ACTIVE
    relationship.activated_at = now
    relationship.suspended_at = None
    relationship.ended_at = None
    relationship.end_reason = None
    relationship.full_clean()
    relationship.save(
        update_fields=[
            "status",
            "activated_at",
            "suspended_at",
            "ended_at",
            "end_reason",
            "updated_at",
        ]
    )

    for organization in (
        relationship.source_organization,
        relationship.target_organization,
    ):
        OrganizationAuditLog.objects.create(
            organization=organization,
            action=OrganizationAuditAction.RELATIONSHIP_ACTIVATED,
            source=OrganizationAuditSource.GOVERNANCE,
            actor=actor,
            relationship=relationship,
            metadata={
                "relationship_id": relationship.id,
                "relationship_public_id": str(relationship.public_id),
                "relationship_type": relationship.relationship_type,
            },
        )

    return relationship


@transaction.atomic
def end_organization_relationship_from_governance(
    *,
    relationship,
    actor=None,
    reason=None,
    now=None,
):
    ensure_organization_hierarchy_enabled()
    now = now or timezone.now()

    relationship = (
        OrganizationRelationship.objects
        .select_for_update()
        .select_related(
            "source_organization",
            "target_organization",
        )
        .get(pk=relationship.pk)
    )

    if relationship.status == OrganizationRelationshipStatus.ENDED:
        return relationship

    if relationship.status != OrganizationRelationshipStatus.ACTIVE:
        raise ValidationError(
            "Only active organization relationships can be ended."
        )

    relationship.status = OrganizationRelationshipStatus.ENDED
    relationship.ended_at = now
    relationship.suspended_at = None
    relationship.end_reason = reason
    relationship.save(
        update_fields=[
            "status",
            "ended_at",
            "suspended_at",
            "end_reason",
            "updated_at",
        ]
    )

    relationship.consents.update(
        status=OrganizationRelationshipConsentStatus.REVOKED,
        decided_at=now,
        updated_at=now,
    )

    dependent_grants = list(
        OrganizationVerificationGrant.objects
        .select_for_update()
        .filter(
            relationship=relationship,
            status=OrganizationVerificationGrantStatus.ACTIVE,
            revoked_at__isnull=True,
        )
    )

    for grant in dependent_grants:
        grant.status = OrganizationVerificationGrantStatus.REVOKED
        grant.revoked_at = now
        grant.revocation_reason = (
            "Supporting organization relationship ended."
        )
        grant.save(
            update_fields=[
                "status",
                "revoked_at",
                "revocation_reason",
                "updated_at",
            ]
        )

        OrganizationAuditLog.objects.create(
            organization=grant.organization,
            action=OrganizationAuditAction.VERIFICATION_REVOKED,
            source=OrganizationAuditSource.GOVERNANCE,
            actor=actor,
            relationship=relationship,
            metadata={
                "verification_grant_id": grant.id,
                "reason": grant.revocation_reason,
            },
        )

    for organization in (
        relationship.source_organization,
        relationship.target_organization,
    ):
        OrganizationAuditLog.objects.create(
            organization=organization,
            action=OrganizationAuditAction.RELATIONSHIP_ENDED,
            source=OrganizationAuditSource.GOVERNANCE,
            actor=actor,
            relationship=relationship,
            metadata={
                "relationship_id": relationship.id,
                "reason": reason,
            },
        )

    return relationship
