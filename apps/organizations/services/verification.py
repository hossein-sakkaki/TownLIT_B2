# apps/organizations/services/verification.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationPermissionKey,
    OrganizationRelationshipStatus,
    OrganizationVerificationDocumentReviewStatus,
    OrganizationVerificationGrantStatus,
    OrganizationVerificationGrantType,
    OrganizationVerificationPath,
    OrganizationVerificationStatus,
)
from apps.organizations.feature_flags import ensure_organization_verification_enabled
from apps.organizations.models import (
    OrganizationAuditLog,
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
    OrganizationVerificationGrant,
)
from apps.organizations.services.access import user_has_organization_permission


def _ensure_verification_manager(*, organization, actor):
    if getattr(actor, "is_staff", False):
        return
    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_VERIFICATION,
    ):
        raise PermissionDenied("You do not have permission to manage organization verification.")


def _ensure_staff_reviewer(actor):
    if not actor or not getattr(actor, "is_staff", False):
        raise PermissionDenied("TownLIT staff review is required for this action.")


def get_active_verification_grant(*, organization, now=None):
    from apps.organizations.selectors.verification import (
        get_active_verification_grant as resolve_active_verification_grant,
    )

    return resolve_active_verification_grant(
        organization=organization,
        now=now,
    )


def models_q_for_current_time(now):
    from django.db.models import Q

    return Q(expires_at__isnull=True) | Q(expires_at__gt=now)


@transaction.atomic
def revoke_dependent_sponsored_grants(
    *,
    sponsor_organization,
    reviewer=None,
    reason=None,
    now=None,
):
    now = now or timezone.now()
    frontier = [sponsor_organization.id]
    visited = set()
    revoked_count = 0

    while frontier:
        sponsor_id = frontier.pop()

        if sponsor_id in visited:
            continue

        visited.add(sponsor_id)

        grants = list(
            OrganizationVerificationGrant.objects
            .select_for_update()
            .select_related("organization")
            .filter(
                grant_type=OrganizationVerificationGrantType.SPONSORED_BRANCH,
                status=OrganizationVerificationGrantStatus.ACTIVE,
                revoked_at__isnull=True,
                relationship__source_organization_id=sponsor_id,
            )
        )

        for grant in grants:
            grant.status = OrganizationVerificationGrantStatus.REVOKED
            grant.revoked_at = now
            grant.revocation_reason = (
                reason
                or "Sponsoring organization verification is no longer active."
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
                source=OrganizationAuditSource.SYSTEM,
                actor=reviewer,
                metadata={
                    "verification_grant_id": grant.id,
                    "reason": grant.revocation_reason,
                    "cascade_from_sponsor_organization_id": sponsor_id,
                },
            )

            revoked_count += 1
            frontier.append(grant.organization_id)

    return revoked_count


@transaction.atomic
def expire_due_verification_grants(*, now=None):
    now = now or timezone.now()
    grant_ids = list(
        OrganizationVerificationGrant.objects
        .filter(
            status=OrganizationVerificationGrantStatus.ACTIVE,
            revoked_at__isnull=True,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .values_list("id", flat=True)
    )

    expired_count = 0

    for grant_id in grant_ids:
        grant = (
            OrganizationVerificationGrant.objects
            .select_for_update()
            .select_related("organization")
            .filter(
                pk=grant_id,
                status=OrganizationVerificationGrantStatus.ACTIVE,
                revoked_at__isnull=True,
            )
            .first()
        )

        if not grant:
            continue

        grant.status = OrganizationVerificationGrantStatus.EXPIRED
        grant.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )
        expired_count += 1

        revoke_dependent_sponsored_grants(
            sponsor_organization=grant.organization,
            reason="Sponsoring organization verification expired.",
            now=now,
        )

    return expired_count


@transaction.atomic
def create_verification_case(
    *,
    organization,
    actor,
    path=OrganizationVerificationPath.DIRECT,
    relationship=None,
    legal_name=None,
    registration_number=None,
    jurisdiction_country=None,
    jurisdiction_region=None,
    registration_authority=None,
    registered_address=None,
    organization_notes=None,
):
    ensure_organization_verification_enabled()
    _ensure_verification_manager(organization=organization, actor=actor)

    expire_due_verification_grants()
    renewal_of = get_active_verification_grant(
        organization=organization,
    )

    case = OrganizationVerificationCase(
        organization=organization,
        path=path,
        renewal_of=renewal_of,
        relationship=relationship,
        legal_name=legal_name,
        registration_number=registration_number,
        jurisdiction_country=jurisdiction_country,
        jurisdiction_region=jurisdiction_region,
        registration_authority=registration_authority,
        registered_address=registered_address,
        organization_notes=organization_notes,
    )
    case.full_clean()
    case.save()

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.VERIFICATION_CASE_CREATED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        metadata={
            "verification_case_id": case.id,
            "verification_case_public_id": str(case.public_id),
            "path": case.path,
            "renewal_of_grant_id": renewal_of.id if renewal_of else None,
            "relationship_id": relationship.id if relationship else None,
        },
    )
    return case


@transaction.atomic
def add_verification_document(
    *,
    verification_case,
    actor,
    document_type,
    file,
    title=None,
    document_number=None,
    issued_at=None,
    expires_at=None,
):
    ensure_organization_verification_enabled()
    verification_case = OrganizationVerificationCase.objects.select_for_update().get(
        pk=verification_case.pk
    )
    _ensure_verification_manager(organization=verification_case.organization, actor=actor)

    if verification_case.status not in {
        OrganizationVerificationStatus.DRAFT,
        OrganizationVerificationStatus.NEEDS_INFORMATION,
    }:
        raise ValidationError("Documents can only be added while the case is editable.")

    document = OrganizationVerificationDocument(
        verification_case=verification_case,
        document_type=document_type,
        file=file,
        title=title,
        document_number=document_number,
        issued_at=issued_at,
        expires_at=expires_at,
        uploaded_by=actor,
    )
    document.full_clean()
    document.save()
    return document


@transaction.atomic
def submit_verification_case(*, verification_case, actor, now=None):
    ensure_organization_verification_enabled()
    now = now or timezone.now()
    verification_case = OrganizationVerificationCase.objects.select_for_update().select_related(
        "organization",
        "relationship__source_organization",
        "renewal_of",
    ).get(pk=verification_case.pk)
    _ensure_verification_manager(organization=verification_case.organization, actor=actor)

    if verification_case.status not in {
        OrganizationVerificationStatus.DRAFT,
        OrganizationVerificationStatus.NEEDS_INFORMATION,
    }:
        raise ValidationError("This verification case cannot be submitted in its current state.")

    if verification_case.path == OrganizationVerificationPath.SPONSORED_BRANCH:
        relationship = verification_case.relationship
        if not relationship or relationship.status != OrganizationRelationshipStatus.ACTIVE:
            raise ValidationError("Sponsored verification requires an active parent or sponsorship relationship.")

        sponsor_grant = get_active_verification_grant(
            organization=relationship.source_organization,
            now=now,
        )
        if not sponsor_grant:
            raise ValidationError("The sponsoring organization must have active verification.")

    if not verification_case.documents.filter(is_active=True).exists():
        raise ValidationError("At least one active verification document is required.")

    verification_case.status = OrganizationVerificationStatus.SUBMITTED
    verification_case.submitted_by = actor
    verification_case.submitted_at = now
    verification_case.review_notes = None
    verification_case.save(
        update_fields=[
            "status", "submitted_by", "submitted_at", "review_notes", "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=verification_case.organization,
        action=OrganizationAuditAction.VERIFICATION_SUBMITTED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        metadata={"verification_case_id": verification_case.id},
    )
    return verification_case


@transaction.atomic
def start_verification_review(*, verification_case, reviewer, now=None):
    ensure_organization_verification_enabled()
    _ensure_staff_reviewer(reviewer)
    now = now or timezone.now()
    verification_case = OrganizationVerificationCase.objects.select_for_update().get(
        pk=verification_case.pk
    )
    if verification_case.status != OrganizationVerificationStatus.SUBMITTED:
        raise ValidationError("Only submitted verification cases can enter review.")

    verification_case.status = OrganizationVerificationStatus.UNDER_REVIEW
    verification_case.reviewed_by = reviewer
    verification_case.review_started_at = now
    verification_case.save(
        update_fields=["status", "reviewed_by", "review_started_at", "updated_at"]
    )
    return verification_case


@transaction.atomic
def mark_verification_needs_information(*, verification_case, reviewer, review_notes, now=None):
    ensure_organization_verification_enabled()
    _ensure_staff_reviewer(reviewer)
    now = now or timezone.now()
    verification_case = OrganizationVerificationCase.objects.select_for_update().get(
        pk=verification_case.pk
    )
    if verification_case.status not in {
        OrganizationVerificationStatus.SUBMITTED,
        OrganizationVerificationStatus.UNDER_REVIEW,
    }:
        raise ValidationError("This verification case cannot request additional information.")

    verification_case.status = OrganizationVerificationStatus.NEEDS_INFORMATION
    verification_case.reviewed_by = reviewer
    verification_case.review_notes = review_notes
    verification_case.decision_at = None
    verification_case.save(
        update_fields=["status", "reviewed_by", "review_notes", "decision_at", "updated_at"]
    )

    OrganizationAuditLog.objects.create(
        organization=verification_case.organization,
        action=OrganizationAuditAction.VERIFICATION_NEEDS_INFORMATION,
        source=OrganizationAuditSource.ADMIN,
        actor=reviewer,
        metadata={"verification_case_id": verification_case.id},
    )
    return verification_case


@transaction.atomic
def review_verification_document(*, document, reviewer, accepted, note=None, now=None):
    ensure_organization_verification_enabled()
    _ensure_staff_reviewer(reviewer)
    now = now or timezone.now()
    document = OrganizationVerificationDocument.objects.select_for_update().select_related(
        "verification_case"
    ).get(pk=document.pk)
    document.review_status = (
        OrganizationVerificationDocumentReviewStatus.ACCEPTED
        if accepted
        else OrganizationVerificationDocumentReviewStatus.REJECTED
    )
    document.review_note = note
    document.reviewed_by = reviewer
    document.reviewed_at = now
    document.save(
        update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at", "updated_at"]
    )
    return document


@transaction.atomic
def approve_verification_case(*, verification_case, reviewer, expires_at=None, now=None):
    ensure_organization_verification_enabled()
    _ensure_staff_reviewer(reviewer)
    now = now or timezone.now()
    verification_case = OrganizationVerificationCase.objects.select_for_update().select_related(
        "organization", "relationship"
    ).get(pk=verification_case.pk)

    if verification_case.status not in {
        OrganizationVerificationStatus.SUBMITTED,
        OrganizationVerificationStatus.UNDER_REVIEW,
    }:
        raise ValidationError("This verification case cannot be approved.")

    active_documents = verification_case.documents.filter(is_active=True)
    if not active_documents.exists():
        raise ValidationError("Verification requires at least one active document.")
    if active_documents.exclude(
        review_status=OrganizationVerificationDocumentReviewStatus.ACCEPTED
    ).exists():
        raise ValidationError(
            "All active verification documents must be reviewed and accepted before approval."
        )

    relationship = verification_case.relationship
    if verification_case.path == OrganizationVerificationPath.SPONSORED_BRANCH:
        if not relationship or relationship.status != OrganizationRelationshipStatus.ACTIVE:
            raise ValidationError("Sponsored verification requires an active relationship.")
        if not get_active_verification_grant(
            organization=relationship.source_organization,
            now=now,
        ):
            raise ValidationError("The sponsoring organization must remain verified.")
        grant_type = OrganizationVerificationGrantType.SPONSORED_BRANCH
    else:
        relationship = None
        grant_type = OrganizationVerificationGrantType.DIRECT

    expire_due_verification_grants(now=now)
    previous_grant = (
        OrganizationVerificationGrant.objects
        .select_for_update()
        .filter(
            organization=verification_case.organization,
            status=OrganizationVerificationGrantStatus.ACTIVE,
            revoked_at__isnull=True,
        )
        .filter(
            models_q_for_current_time(now)
        )
        .order_by("-granted_at")
        .first()
    )

    if previous_grant:
        previous_grant.status = OrganizationVerificationGrantStatus.SUPERSEDED
        previous_grant.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    grant = OrganizationVerificationGrant(
        organization=verification_case.organization,
        verification_case=verification_case,
        grant_type=grant_type,
        relationship=relationship,
        supersedes=previous_grant,
        granted_by=reviewer,
        granted_at=now,
        expires_at=expires_at,
    )
    grant.full_clean()
    grant.save()

    verification_case.status = OrganizationVerificationStatus.APPROVED
    verification_case.reviewed_by = reviewer
    verification_case.decision_at = now
    verification_case.save(
        update_fields=["status", "reviewed_by", "decision_at", "updated_at"]
    )

    OrganizationAuditLog.objects.create(
        organization=verification_case.organization,
        action=OrganizationAuditAction.VERIFICATION_APPROVED,
        source=OrganizationAuditSource.ADMIN,
        actor=reviewer,
        metadata={
            "verification_case_id": verification_case.id,
            "verification_grant_id": grant.id,
            "grant_type": grant.grant_type,
            "supersedes_grant_id": previous_grant.id if previous_grant else None,
        },
    )
    return grant


@transaction.atomic
def reject_verification_case(*, verification_case, reviewer, review_notes, now=None):
    ensure_organization_verification_enabled()
    _ensure_staff_reviewer(reviewer)
    now = now or timezone.now()
    verification_case = OrganizationVerificationCase.objects.select_for_update().get(
        pk=verification_case.pk
    )
    if verification_case.status not in {
        OrganizationVerificationStatus.SUBMITTED,
        OrganizationVerificationStatus.UNDER_REVIEW,
        OrganizationVerificationStatus.NEEDS_INFORMATION,
    }:
        raise ValidationError("This verification case cannot be rejected.")

    verification_case.status = OrganizationVerificationStatus.REJECTED
    verification_case.reviewed_by = reviewer
    verification_case.review_notes = review_notes
    verification_case.decision_at = now
    verification_case.save(
        update_fields=["status", "reviewed_by", "review_notes", "decision_at", "updated_at"]
    )

    OrganizationAuditLog.objects.create(
        organization=verification_case.organization,
        action=OrganizationAuditAction.VERIFICATION_REJECTED,
        source=OrganizationAuditSource.ADMIN,
        actor=reviewer,
        metadata={"verification_case_id": verification_case.id},
    )
    return verification_case


@transaction.atomic
def withdraw_verification_case(*, verification_case, actor, now=None):
    ensure_organization_verification_enabled()
    now = now or timezone.now()
    verification_case = OrganizationVerificationCase.objects.select_for_update().get(
        pk=verification_case.pk
    )
    _ensure_verification_manager(organization=verification_case.organization, actor=actor)
    if verification_case.status not in {
        OrganizationVerificationStatus.DRAFT,
        OrganizationVerificationStatus.SUBMITTED,
        OrganizationVerificationStatus.NEEDS_INFORMATION,
    }:
        raise ValidationError("This verification case cannot be withdrawn.")

    verification_case.status = OrganizationVerificationStatus.WITHDRAWN
    verification_case.decision_at = now
    verification_case.save(update_fields=["status", "decision_at", "updated_at"])
    OrganizationAuditLog.objects.create(
        organization=verification_case.organization,
        action=OrganizationAuditAction.VERIFICATION_WITHDRAWN,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        metadata={"verification_case_id": verification_case.id},
    )
    return verification_case


@transaction.atomic
def revoke_verification_grant(*, grant, reviewer, reason, now=None):
    ensure_organization_verification_enabled()
    _ensure_staff_reviewer(reviewer)
    now = now or timezone.now()
    grant = OrganizationVerificationGrant.objects.select_for_update().select_related(
        "organization"
    ).get(pk=grant.pk)
    if grant.status != OrganizationVerificationGrantStatus.ACTIVE:
        return grant

    grant.status = OrganizationVerificationGrantStatus.REVOKED
    grant.revoked_at = now
    grant.revocation_reason = reason
    grant.save(update_fields=["status", "revoked_at", "revocation_reason", "updated_at"])

    OrganizationAuditLog.objects.create(
        organization=grant.organization,
        action=OrganizationAuditAction.VERIFICATION_REVOKED,
        source=OrganizationAuditSource.ADMIN,
        actor=reviewer,
        metadata={"verification_grant_id": grant.id, "reason": reason},
    )
    revoke_dependent_sponsored_grants(
        sponsor_organization=grant.organization,
        reviewer=reviewer,
        reason="Sponsoring organization verification was revoked.",
        now=now,
    )
    return grant
