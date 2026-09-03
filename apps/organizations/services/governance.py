# apps/organizations/services/governance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    DEFAULT_GOVERNANCE_RULES,
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationGovernanceAction,
    OrganizationGovernanceDecisionResult,
    OrganizationGovernanceElectorateType,
    OrganizationGovernanceProposalStatus,
    OrganizationGovernanceVoteChoice,
    OrganizationMembershipStatus,
    OrganizationPermissionKey,
    OrganizationRelationshipConsentStatus,
    OrganizationRelationshipStatus,
    OrganizationRoleKey,
    OrganizationRoleScope,
    OrganizationStatus,
)
from apps.organizations.feature_flags import (
    ensure_organization_governance_enabled,
)
from apps.organizations.models import (
    OrganizationAuditLog,
    OrganizationGovernanceDecision,
    OrganizationGovernanceElector,
    OrganizationGovernanceProposal,
    OrganizationGovernanceRule,
    OrganizationGovernanceVote,
    OrganizationGovernanceVoteRevision,
    OrganizationMembership,
    OrganizationRelationshipConsent,
    OrganizationRoleAssignment,
)
from apps.organizations.services.access import (
    get_current_membership_for_user,
    user_has_organization_permission,
)
from apps.organizations.services.roles import (
    assign_organization_role,
    get_owner_role,
    revoke_organization_role,
)


def bootstrap_organization_governance(organization):
    rules = {}

    for definition in DEFAULT_GOVERNANCE_RULES:
        defaults = {
            key: value
            for key, value in definition.items()
            if key != "action_key"
        }

        rule, _ = OrganizationGovernanceRule.objects.get_or_create(
            organization=organization,
            action_key=definition["action_key"],
            defaults=defaults,
        )

        rules[rule.action_key] = rule

    return rules


def _ensure_manage_governance(*, actor, organization):
    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_GOVERNANCE,
    ):
        raise PermissionDenied(
            "You do not have permission to manage organization governance."
        )


def _validate_proposal_target(
    *,
    organization,
    action_key,
    target_membership=None,
    relationship=None,
):
    if (
        target_membership
        and target_membership.organization_id != organization.id
    ):
        raise ValidationError(
            "Target membership belongs to a different organization."
        )

    if relationship and organization.id not in {
        relationship.source_organization_id,
        relationship.target_organization_id,
    }:
        raise ValidationError(
            "Target relationship does not include this organization."
        )

    if action_key == OrganizationGovernanceAction.OWNER_ADDITION:
        if not target_membership:
            raise ValidationError(
                "Owner addition requires a target membership."
            )

        if target_membership.status != OrganizationMembershipStatus.ACTIVE:
            raise ValidationError(
                "Only active members can become owners."
            )

        owner_role = get_owner_role(organization)

        if target_membership.role_assignments.filter(
            role=owner_role,
            is_active=True,
            revoked_at__isnull=True,
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        ).exists():
            raise ValidationError(
                "Target membership is already an organization owner."
            )

    elif action_key == OrganizationGovernanceAction.OWNER_REMOVAL:
        if not target_membership:
            raise ValidationError(
                "Owner removal requires a target membership."
            )

        owner_role = get_owner_role(organization)

        if not target_membership.role_assignments.filter(
            role=owner_role,
            is_active=True,
            revoked_at__isnull=True,
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        ).exists():
            raise ValidationError(
                "Target membership is not an active organization owner."
            )

    elif action_key == OrganizationGovernanceAction.ORGANIZATION_CLOSURE:
        if organization.status != OrganizationStatus.ACTIVE:
            raise ValidationError(
                "Only active organizations can be closed through governance."
            )

    elif action_key == OrganizationGovernanceAction.ORGANIZATION_RESTORATION:
        if organization.status != OrganizationStatus.CLOSED:
            raise ValidationError(
                "Only closed organizations can be restored through governance."
            )

    elif action_key == OrganizationGovernanceAction.RELATIONSHIP_CONSENT:
        if not relationship:
            raise ValidationError(
                "Relationship consent requires a relationship."
            )

        if relationship.status != OrganizationRelationshipStatus.PENDING:
            raise ValidationError(
                "Only pending relationships can receive governance consent."
            )

        consent = OrganizationRelationshipConsent.objects.filter(
            relationship=relationship,
            organization=organization,
            status=OrganizationRelationshipConsentStatus.PENDING,
        ).first()

        if not consent:
            raise ValidationError(
                "This organization does not have pending relationship consent."
            )

    elif action_key == OrganizationGovernanceAction.RELATIONSHIP_ENDING:
        if not relationship:
            raise ValidationError(
                "Relationship ending requires a relationship."
            )

        if relationship.status != OrganizationRelationshipStatus.ACTIVE:
            raise ValidationError(
                "Only active relationships can be ended through governance."
            )


def _rule_snapshot(rule):
    return {
        "action_key": rule.action_key,
        "electorate_type": rule.electorate_type,
        "electorate_role_id": rule.electorate_role_id,
        "electorate_role_key": (
            rule.electorate_role.key
            if rule.electorate_role_id
            else None
        ),
        "quorum_percent": str(rule.quorum_percent),
        "approval_percent": str(rule.approval_percent),
        "minimum_electors": rule.minimum_electors,
        "voting_period_hours": rule.voting_period_hours,
        "allow_abstain": rule.allow_abstain,
        "allow_vote_changes": rule.allow_vote_changes,
        "exclude_target_membership": rule.exclude_target_membership,
    }


def _active_role_assignments_queryset(*, organization, now):
    return (
        OrganizationRoleAssignment.objects
        .filter(
            membership__organization=organization,
            membership__status=OrganizationMembershipStatus.ACTIVE,
            is_active=True,
            revoked_at__isnull=True,
            starts_at__lte=now,
            role__is_active=True,
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gt=now)
        )
    )


def _elector_memberships(*, proposal, rule, now):
    base = OrganizationMembership.objects.filter(
        organization=proposal.organization,
        status=OrganizationMembershipStatus.ACTIVE,
    )

    if rule.electorate_type == OrganizationGovernanceElectorateType.ACTIVE_MEMBERS:
        queryset = base

    elif rule.electorate_type == OrganizationGovernanceElectorateType.OWNERS:
        owner_role = get_owner_role(proposal.organization)
        membership_ids = (
            _active_role_assignments_queryset(
                organization=proposal.organization,
                now=now,
            )
            .filter(role=owner_role)
            .values_list("membership_id", flat=True)
        )
        queryset = base.filter(id__in=membership_ids)

    elif rule.electorate_type == OrganizationGovernanceElectorateType.ROLE:
        if not rule.electorate_role_id:
            raise ValidationError(
                "Role-based governance requires an electorate role."
            )

        membership_ids = (
            _active_role_assignments_queryset(
                organization=proposal.organization,
                now=now,
            )
            .filter(role=rule.electorate_role)
            .values_list("membership_id", flat=True)
        )
        queryset = base.filter(id__in=membership_ids)

    else:
        raise ValidationError(
            "Unsupported governance electorate type."
        )

    if rule.exclude_target_membership and proposal.target_membership_id:
        queryset = queryset.exclude(pk=proposal.target_membership_id)

    return (
        queryset
        .select_related("member__user")
        .distinct()
        .order_by("id")
    )


@transaction.atomic
def create_governance_proposal(
    *,
    organization,
    action_key,
    title,
    actor,
    rationale=None,
    target_membership=None,
    relationship=None,
    payload=None,
    open_immediately=False,
    now=None,
):
    ensure_organization_governance_enabled()
    now = now or timezone.now()

    _ensure_manage_governance(
        actor=actor,
        organization=organization,
    )

    rules = bootstrap_organization_governance(organization)
    rule = rules.get(action_key)

    if not rule or not rule.is_active:
        raise ValidationError(
            "Governance is not configured for this action."
        )

    _validate_proposal_target(
        organization=organization,
        action_key=action_key,
        target_membership=target_membership,
        relationship=relationship,
    )

    proposed_by_membership = get_current_membership_for_user(
        organization=organization,
        user=actor,
    )

    proposal = OrganizationGovernanceProposal(
        organization=organization,
        rule=rule,
        action_key=action_key,
        title=title,
        rationale=rationale,
        target_membership=target_membership,
        relationship=relationship,
        proposed_by_membership=proposed_by_membership,
        payload=payload or {},
        created_by=actor,
    )
    proposal.full_clean()

    try:
        with transaction.atomic():
            proposal.save()
    except IntegrityError as exc:
        raise ValidationError(
            "An open governance proposal already exists for this action and subject."
        ) from exc

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.GOVERNANCE_PROPOSAL_CREATED,
        source=OrganizationAuditSource.GOVERNANCE,
        actor=actor,
        membership=proposed_by_membership,
        relationship=relationship,
        governance_proposal=proposal,
        metadata={
            "action_key": action_key,
            "target_membership_id": (
                target_membership.id
                if target_membership
                else None
            ),
        },
    )

    if open_immediately:
        return open_governance_proposal(
            proposal=proposal,
            actor=actor,
            now=now,
        )

    return proposal


@transaction.atomic
def open_governance_proposal(*, proposal, actor, now=None):
    ensure_organization_governance_enabled()
    now = now or timezone.now()

    proposal = (
        OrganizationGovernanceProposal.objects
        .select_for_update()
        .select_related(
            "organization",
            "rule__electorate_role",
            "target_membership",
            "relationship",
        )
        .get(pk=proposal.pk)
    )

    _ensure_manage_governance(
        actor=actor,
        organization=proposal.organization,
    )

    if proposal.status != OrganizationGovernanceProposalStatus.DRAFT:
        raise ValidationError(
            "Only draft proposals can be opened."
        )

    _validate_proposal_target(
        organization=proposal.organization,
        action_key=proposal.action_key,
        target_membership=proposal.target_membership,
        relationship=proposal.relationship,
    )

    rule = proposal.rule
    electors = list(
        _elector_memberships(
            proposal=proposal,
            rule=rule,
            now=now,
        )
    )

    if len(electors) < rule.minimum_electors:
        raise ValidationError(
            "The proposal does not have enough eligible electors."
        )

    for membership in electors:
        role_keys = list(
            membership.role_assignments
            .filter(
                is_active=True,
                revoked_at__isnull=True,
                starts_at__lte=now,
                role__is_active=True,
            )
            .filter(
                Q(ends_at__isnull=True)
                | Q(ends_at__gt=now)
            )
            .values_list("role__key", flat=True)
            .distinct()
        )

        elector = OrganizationGovernanceElector(
            proposal=proposal,
            membership=membership,
            user=membership.member.user,
            membership_id_snapshot=membership.id,
            role_keys_snapshot=role_keys,
            vote_weight=Decimal("1.000"),
        )
        elector.full_clean()
        elector.save()

    proposal.status = OrganizationGovernanceProposalStatus.OPEN
    proposal.rule_snapshot = _rule_snapshot(rule)
    proposal.opened_at = now
    proposal.closes_at = now + timedelta(
        hours=rule.voting_period_hours
    )
    proposal.save(
        update_fields=[
            "status",
            "rule_snapshot",
            "opened_at",
            "closes_at",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=proposal.organization,
        action=OrganizationAuditAction.GOVERNANCE_PROPOSAL_OPENED,
        source=OrganizationAuditSource.GOVERNANCE,
        actor=actor,
        governance_proposal=proposal,
        relationship=proposal.relationship,
        metadata={
            "eligible_count": len(electors),
            "closes_at": proposal.closes_at.isoformat(),
        },
    )

    return proposal


@transaction.atomic
def cast_governance_vote(*, actor, proposal, choice, now=None):
    ensure_organization_governance_enabled()
    now = now or timezone.now()

    proposal = (
        OrganizationGovernanceProposal.objects
        .select_for_update()
        .select_related("organization")
        .get(pk=proposal.pk)
    )

    if proposal.status != OrganizationGovernanceProposalStatus.OPEN:
        raise ValidationError(
            "This proposal is not open for voting."
        )

    if proposal.opened_at and now < proposal.opened_at:
        raise ValidationError(
            "Voting has not opened yet."
        )

    if proposal.closes_at and now >= proposal.closes_at:
        raise ValidationError(
            "Voting has closed."
        )

    if choice not in OrganizationGovernanceVoteChoice.values:
        raise ValidationError({
            "choice": "Invalid governance vote choice.",
        })

    if (
        choice == OrganizationGovernanceVoteChoice.ABSTAIN
        and not proposal.rule_snapshot.get("allow_abstain", True)
    ):
        raise ValidationError(
            "Abstention is not allowed for this proposal."
        )

    elector = (
        OrganizationGovernanceElector.objects
        .select_for_update()
        .filter(
            proposal=proposal,
            user=actor,
            is_eligible=True,
        )
        .first()
    )

    if not elector:
        raise PermissionDenied(
            "You are not an eligible elector for this proposal."
        )

    vote = OrganizationGovernanceVote.objects.filter(
        elector=elector,
    ).first()

    previous_choice = vote.choice if vote else None

    if vote and not proposal.rule_snapshot.get(
        "allow_vote_changes",
        False,
    ):
        raise ValidationError(
            "This governance vote cannot be changed."
        )

    if vote:
        vote.choice = choice
        vote.cast_by = actor
        vote.cast_at = now
        vote.full_clean()
        vote.save(
            update_fields=[
                "choice",
                "cast_by",
                "cast_at",
                "updated_at",
            ]
        )
    else:
        vote = OrganizationGovernanceVote(
            proposal=proposal,
            elector=elector,
            choice=choice,
            cast_by=actor,
            cast_at=now,
        )
        vote.full_clean()
        vote.save()

    revision = OrganizationGovernanceVoteRevision(
        vote=vote,
        previous_choice=previous_choice,
        new_choice=choice,
        actor=actor,
    )
    revision.full_clean()
    revision.save()

    OrganizationAuditLog.objects.create(
        organization=proposal.organization,
        action=OrganizationAuditAction.GOVERNANCE_VOTE_CAST,
        source=OrganizationAuditSource.GOVERNANCE,
        actor=actor,
        governance_proposal=proposal,
        metadata={
            "choice": choice,
            "changed": previous_choice is not None,
        },
    )

    return vote


def _compute_decision(*, proposal, now):
    electors = list(
        proposal.electors.filter(is_eligible=True)
    )
    votes = list(
        proposal.votes
        .select_related("elector")
        .filter(elector__is_eligible=True)
    )

    eligible_weight = sum(
        (elector.vote_weight for elector in electors),
        Decimal("0.000"),
    )
    participating_weight = sum(
        (vote.elector.vote_weight for vote in votes),
        Decimal("0.000"),
    )

    approve_votes = [
        vote
        for vote in votes
        if vote.choice == OrganizationGovernanceVoteChoice.APPROVE
    ]
    reject_votes = [
        vote
        for vote in votes
        if vote.choice == OrganizationGovernanceVoteChoice.REJECT
    ]
    abstain_votes = [
        vote
        for vote in votes
        if vote.choice == OrganizationGovernanceVoteChoice.ABSTAIN
    ]

    approve_weight = sum(
        (vote.elector.vote_weight for vote in approve_votes),
        Decimal("0.000"),
    )
    reject_weight = sum(
        (vote.elector.vote_weight for vote in reject_votes),
        Decimal("0.000"),
    )
    abstain_weight = sum(
        (vote.elector.vote_weight for vote in abstain_votes),
        Decimal("0.000"),
    )

    quorum_percent = Decimal(
        str(proposal.rule_snapshot["quorum_percent"])
    )
    approval_percent = Decimal(
        str(proposal.rule_snapshot["approval_percent"])
    )

    quorum_required_weight = (
        eligible_weight
        * quorum_percent
        / Decimal("100")
    )

    decisive_weight = approve_weight + reject_weight
    approval_required_weight = (
        decisive_weight
        * approval_percent
        / Decimal("100")
    )

    percentage_quantum = Decimal("0.01")
    participation_percent = (
        (
            participating_weight
            * Decimal("100")
            / eligible_weight
        ).quantize(
            percentage_quantum,
            rounding=ROUND_HALF_UP,
        )
        if eligible_weight > 0
        else Decimal("0.00")
    )
    approval_percent_actual = (
        (
            approve_weight
            * Decimal("100")
            / decisive_weight
        ).quantize(
            percentage_quantum,
            rounding=ROUND_HALF_UP,
        )
        if decisive_weight > 0
        else Decimal("0.00")
    )

    minimum_electors = int(
        proposal.rule_snapshot.get("minimum_electors", 1)
    )

    if len(electors) < minimum_electors:
        result = OrganizationGovernanceDecisionResult.INSUFFICIENT_ELECTORATE
        quorum_met = False
        approval_met = False
    else:
        quorum_met = participation_percent >= quorum_percent
        approval_met = (
            decisive_weight > 0
            and approval_percent_actual >= approval_percent
        )

        if not quorum_met:
            result = OrganizationGovernanceDecisionResult.NO_QUORUM
        elif approval_met:
            result = OrganizationGovernanceDecisionResult.APPROVED
        else:
            result = OrganizationGovernanceDecisionResult.REJECTED

    return {
        "result": result,
        "eligible_count": len(electors),
        "participating_count": len(votes),
        "approve_count": len(approve_votes),
        "reject_count": len(reject_votes),
        "abstain_count": len(abstain_votes),
        "eligible_weight": eligible_weight,
        "participating_weight": participating_weight,
        "approve_weight": approve_weight,
        "reject_weight": reject_weight,
        "abstain_weight": abstain_weight,
        "quorum_required_weight": quorum_required_weight,
        "approval_required_weight": approval_required_weight,
        "quorum_percent_snapshot": quorum_percent,
        "approval_percent_snapshot": approval_percent,
        "participation_percent": participation_percent,
        "approval_percent_actual": approval_percent_actual,
        "quorum_met": quorum_met,
        "approval_met": approval_met,
        "decided_at": now,
    }


def _execute_approved_proposal(*, proposal, actor, now):
    action_key = proposal.action_key

    if action_key == OrganizationGovernanceAction.OWNER_ADDITION:
        owner_role = get_owner_role(proposal.organization)

        return assign_organization_role(
            membership=proposal.target_membership,
            role=owner_role,
            actor=actor,
            bypass_protection=True,
        )

    if action_key == OrganizationGovernanceAction.OWNER_REMOVAL:
        owner_role = get_owner_role(proposal.organization)

        active_owner_assignments = (
            _active_role_assignments_queryset(
                organization=proposal.organization,
                now=now,
            )
            .filter(role=owner_role)
        )

        if active_owner_assignments.count() <= 1:
            raise ValidationError(
                "The final organization owner cannot be removed."
            )

        assignment = active_owner_assignments.get(
            membership=proposal.target_membership,
        )

        return revoke_organization_role(
            assignment=assignment,
            actor=actor,
            bypass_protection=True,
            now=now,
        )

    if action_key == OrganizationGovernanceAction.ORGANIZATION_CLOSURE:
        organization = proposal.organization
        organization.status = OrganizationStatus.CLOSED
        organization.closed_at = now
        organization.save(
            update_fields=[
                "status",
                "closed_at",
                "updated_at",
            ]
        )
        return organization

    if action_key == OrganizationGovernanceAction.ORGANIZATION_RESTORATION:
        organization = proposal.organization
        organization.status = OrganizationStatus.ACTIVE
        organization.closed_at = None
        organization.save(
            update_fields=[
                "status",
                "closed_at",
                "updated_at",
            ]
        )
        return organization

    if action_key == OrganizationGovernanceAction.RELATIONSHIP_CONSENT:
        from apps.organizations.services.hierarchy import (
            apply_relationship_consent_decision_from_governance,
        )

        return apply_relationship_consent_decision_from_governance(
            relationship=proposal.relationship,
            organization=proposal.organization,
            approved=True,
            actor=actor,
            now=now,
        )

    if action_key == OrganizationGovernanceAction.RELATIONSHIP_ENDING:
        from apps.organizations.services.hierarchy import (
            end_organization_relationship_from_governance,
        )

        return end_organization_relationship_from_governance(
            relationship=proposal.relationship,
            actor=actor,
            reason=proposal.rationale,
            now=now,
        )

    raise ValidationError(
        "Unsupported governance execution action."
    )


@transaction.atomic
def finalize_governance_proposal(
    *,
    proposal,
    actor=None,
    now=None,
    allow_early_if_all_voted=True,
):
    ensure_organization_governance_enabled()
    now = now or timezone.now()

    proposal = (
        OrganizationGovernanceProposal.objects
        .select_for_update()
        .select_related(
            "organization",
            "target_membership",
            "relationship",
            "created_by",
        )
        .get(pk=proposal.pk)
    )

    if actor is not None:
        _ensure_manage_governance(
            actor=actor,
            organization=proposal.organization,
        )

    if hasattr(proposal, "decision"):
        return proposal.decision

    if proposal.status != OrganizationGovernanceProposalStatus.OPEN:
        raise ValidationError(
            "Only open proposals can be finalized."
        )

    eligible_count = proposal.electors.filter(
        is_eligible=True,
    ).count()
    votes_cast = proposal.votes.filter(
        elector__is_eligible=True,
    ).count()

    if proposal.closes_at and now < proposal.closes_at:
        if not (
            allow_early_if_all_voted
            and eligible_count > 0
            and votes_cast == eligible_count
        ):
            raise ValidationError(
                "This proposal cannot be finalized before voting closes."
            )

    result_data = _compute_decision(
        proposal=proposal,
        now=now,
    )

    decision = OrganizationGovernanceDecision.objects.create(
        proposal=proposal,
        **result_data,
        metadata={
            "rule_snapshot": proposal.rule_snapshot,
        },
    )

    proposal.decided_at = now
    proposal.status = (
        OrganizationGovernanceProposalStatus.APPROVED
        if decision.result == OrganizationGovernanceDecisionResult.APPROVED
        else OrganizationGovernanceProposalStatus.REJECTED
    )
    proposal.save(
        update_fields=[
            "status",
            "decided_at",
            "updated_at",
        ]
    )

    execution_actor = actor or proposal.created_by

    OrganizationAuditLog.objects.create(
        organization=proposal.organization,
        action=OrganizationAuditAction.GOVERNANCE_DECIDED,
        source=OrganizationAuditSource.GOVERNANCE,
        actor=execution_actor,
        governance_proposal=proposal,
        relationship=proposal.relationship,
        metadata={
            "result": decision.result,
            "quorum_met": decision.quorum_met,
            "approval_met": decision.approval_met,
        },
    )

    if decision.result != OrganizationGovernanceDecisionResult.APPROVED:
        # Explicit rejection ends pending relationship consent.
        if (
            proposal.action_key
            == OrganizationGovernanceAction.RELATIONSHIP_CONSENT
            and decision.result
            == OrganizationGovernanceDecisionResult.REJECTED
        ):
            from apps.organizations.services.hierarchy import (
                apply_relationship_consent_decision_from_governance,
            )

            apply_relationship_consent_decision_from_governance(
                relationship=proposal.relationship,
                organization=proposal.organization,
                approved=False,
                actor=execution_actor,
                note="Relationship consent was rejected by governance.",
                now=now,
            )

        return decision

    try:
        with transaction.atomic():
            _execute_approved_proposal(
                proposal=proposal,
                actor=execution_actor,
                now=now,
            )
    except Exception as exc:
        proposal.status = OrganizationGovernanceProposalStatus.EXECUTION_FAILED
        proposal.execution_error = str(exc)[:4000]
        proposal.save(
            update_fields=[
                "status",
                "execution_error",
                "updated_at",
            ]
        )

        OrganizationAuditLog.objects.create(
            organization=proposal.organization,
            action=OrganizationAuditAction.GOVERNANCE_EXECUTION_FAILED,
            source=OrganizationAuditSource.GOVERNANCE,
            actor=execution_actor,
            governance_proposal=proposal,
            relationship=proposal.relationship,
            metadata={
                "error": proposal.execution_error,
            },
        )

        return decision

    proposal.status = OrganizationGovernanceProposalStatus.EXECUTED
    proposal.executed_at = now
    proposal.execution_error = None
    proposal.save(
        update_fields=[
            "status",
            "executed_at",
            "execution_error",
            "updated_at",
        ]
    )

    OrganizationAuditLog.objects.create(
        organization=proposal.organization,
        action=OrganizationAuditAction.GOVERNANCE_EXECUTED,
        source=OrganizationAuditSource.GOVERNANCE,
        actor=execution_actor,
        governance_proposal=proposal,
        relationship=proposal.relationship,
        metadata={
            "action_key": proposal.action_key,
        },
    )

    return decision


@transaction.atomic
def cancel_governance_proposal(*, proposal, actor, now=None):
    ensure_organization_governance_enabled()
    now = now or timezone.now()

    proposal = (
        OrganizationGovernanceProposal.objects
        .select_for_update()
        .select_related("organization")
        .get(pk=proposal.pk)
    )

    _ensure_manage_governance(
        actor=actor,
        organization=proposal.organization,
    )

    if proposal.status not in {
        OrganizationGovernanceProposalStatus.DRAFT,
        OrganizationGovernanceProposalStatus.OPEN,
    }:
        raise ValidationError(
            "This proposal can no longer be canceled."
        )

    proposal.status = OrganizationGovernanceProposalStatus.CANCELED
    proposal.decided_at = now
    proposal.save(
        update_fields=[
            "status",
            "decided_at",
            "updated_at",
        ]
    )

    return proposal
