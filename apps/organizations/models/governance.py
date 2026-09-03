# apps/organizations/models/governance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationGovernanceAction,
    OrganizationGovernanceDecisionResult,
    OrganizationGovernanceElectorateType,
    OrganizationGovernanceProposalStatus,
    OrganizationGovernanceVoteChoice,
)


OPEN_PROPOSAL_STATUSES = (
    OrganizationGovernanceProposalStatus.DRAFT,
    OrganizationGovernanceProposalStatus.OPEN,
)


class OrganizationGovernanceRule(models.Model):
    id = models.BigAutoField(primary_key=True)

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="governance_rules",
    )
    action_key = models.CharField(
        max_length=50,
        choices=OrganizationGovernanceAction.choices,
        db_index=True,
    )
    electorate_type = models.CharField(
        max_length=30,
        choices=OrganizationGovernanceElectorateType.choices,
        default=OrganizationGovernanceElectorateType.OWNERS,
    )
    electorate_role = models.ForeignKey(
        "organizations.OrganizationRole",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="governance_rules",
    )
    quorum_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="100.00",
    )
    approval_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="66.67",
    )
    minimum_electors = models.PositiveSmallIntegerField(default=1)
    voting_period_hours = models.PositiveIntegerField(default=72)
    allow_abstain = models.BooleanField(default=True)
    allow_vote_changes = models.BooleanField(default=False)
    exclude_target_membership = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Governance Rule"
        verbose_name_plural = "Organization Governance Rules"
        ordering = ("action_key",)
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "action_key"],
                name="organizations_unique_governance_rule",
            ),
            models.CheckConstraint(
                check=Q(quorum_percent__gte=0) & Q(quorum_percent__lte=100),
                name="organizations_governance_quorum_range",
            ),
            models.CheckConstraint(
                check=Q(approval_percent__gte=0) & Q(approval_percent__lte=100),
                name="organizations_governance_approval_range",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.electorate_type == OrganizationGovernanceElectorateType.ROLE
            and not self.electorate_role_id
        ):
            raise ValidationError({
                "electorate_role": "Role electorate requires an organization role.",
            })

        if (
            self.electorate_role_id
            and self.electorate_role.organization_id != self.organization_id
        ):
            raise ValidationError({
                "electorate_role": "Electorate role must belong to this organization.",
            })

    def __str__(self):
        return f"{self.organization_id}:{self.action_key}"


class OrganizationGovernanceProposal(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="governance_proposals",
    )
    rule = models.ForeignKey(
        OrganizationGovernanceRule,
        on_delete=models.PROTECT,
        related_name="proposals",
    )
    action_key = models.CharField(
        max_length=50,
        choices=OrganizationGovernanceAction.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=OrganizationGovernanceProposalStatus.choices,
        default=OrganizationGovernanceProposalStatus.DRAFT,
        db_index=True,
    )

    # MySQL-safe uniqueness for an in-flight action/subject pair.
    open_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    subject_key = models.CharField(
        max_length=120,
        default="global",
        editable=False,
        db_index=True,
    )

    title = models.CharField(max_length=240)
    rationale = models.TextField(null=True, blank=True)

    target_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="governance_proposals_as_target",
    )
    relationship = models.ForeignKey(
        "organizations.OrganizationRelationship",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="governance_proposals",
    )
    proposed_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="governance_proposals_created",
    )

    payload = models.JSONField(default=dict, blank=True)
    rule_snapshot = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_organization_governance_proposals",
    )
    opened_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closes_at = models.DateTimeField(null=True, blank=True, db_index=True)
    decided_at = models.DateTimeField(null=True, blank=True, db_index=True)
    executed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    execution_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Governance Proposal"
        verbose_name_plural = "Organization Governance Proposals"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "action_key", "subject_key", "open_slot"],
                name="organizations_unique_open_governance_action",
            ),
            models.CheckConstraint(
                check=(
                    Q(closes_at__isnull=True)
                    | Q(opened_at__isnull=True)
                    | Q(closes_at__gt=models.F("opened_at"))
                ),
                name="organizations_governance_voting_window",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["status", "closes_at"]),
        ]

    def _sync_internal_fields(self):
        self.open_slot = 1 if self.status in OPEN_PROPOSAL_STATUSES else None

        if self.target_membership_id:
            self.subject_key = f"membership:{self.target_membership_id}"
        elif self.relationship_id:
            self.subject_key = f"relationship:{self.relationship_id}"
        else:
            self.subject_key = "global"

    def clean(self):
        super().clean()
        self._sync_internal_fields()

        if self.rule_id and self.rule.organization_id != self.organization_id:
            raise ValidationError({
                "rule": "Governance rule must belong to this organization.",
            })

        if self.rule_id and self.rule.action_key != self.action_key:
            raise ValidationError({
                "rule": "Governance rule action does not match proposal action.",
            })

        if (
            self.target_membership_id
            and self.target_membership.organization_id != self.organization_id
        ):
            raise ValidationError({
                "target_membership": "Target membership must belong to this organization.",
            })

        if self.relationship_id and self.organization_id not in {
            self.relationship.source_organization_id,
            self.relationship.target_organization_id,
        }:
            raise ValidationError({
                "relationship": "Proposal organization must be a relationship party.",
            })

        if (
            self.proposed_by_membership_id
            and self.proposed_by_membership.organization_id != self.organization_id
        ):
            raise ValidationError({
                "proposed_by_membership": "Proposal membership must belong to this organization.",
            })

    def save(self, *args, **kwargs):
        self._sync_internal_fields()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update({"open_slot", "subject_key"})
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization_id}:{self.action_key}:{self.status}"


class OrganizationGovernanceElector(models.Model):
    id = models.BigAutoField(primary_key=True)

    proposal = models.ForeignKey(
        OrganizationGovernanceProposal,
        on_delete=models.CASCADE,
        related_name="electors",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="governance_elector_snapshots",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_governance_elector_snapshots",
    )

    membership_id_snapshot = models.PositiveBigIntegerField()
    role_keys_snapshot = models.JSONField(default=list, blank=True)
    vote_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default="1.000",
    )
    is_eligible = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Organization Governance Elector"
        verbose_name_plural = "Organization Governance Electors"
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "membership"],
                name="organizations_unique_governance_elector_membership",
            ),
            models.UniqueConstraint(
                fields=["proposal", "user"],
                name="organizations_unique_governance_elector_user",
            ),
            models.CheckConstraint(
                check=Q(vote_weight__gt=0),
                name="organizations_governance_vote_weight_positive",
            ),
        ]

    def clean(self):
        super().clean()

        if self.membership.organization_id != self.proposal.organization_id:
            raise ValidationError(
                "Elector membership must belong to the proposal organization."
            )

        if self.membership.member.user_id != self.user_id:
            raise ValidationError(
                "Elector user must match the membership user."
            )

        if self.membership_id_snapshot != self.membership_id:
            raise ValidationError(
                "Membership snapshot must match the elector membership."
            )

    def __str__(self):
        return f"{self.proposal_id}:{self.membership_id}"


class OrganizationGovernanceVote(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    proposal = models.ForeignKey(
        OrganizationGovernanceProposal,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    elector = models.OneToOneField(
        OrganizationGovernanceElector,
        on_delete=models.PROTECT,
        related_name="vote",
    )
    choice = models.CharField(
        max_length=20,
        choices=OrganizationGovernanceVoteChoice.choices,
        db_index=True,
    )
    cast_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_governance_votes",
    )
    cast_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Governance Vote"
        verbose_name_plural = "Organization Governance Votes"
        ordering = ("cast_at",)

    def clean(self):
        super().clean()

        if self.elector.proposal_id != self.proposal_id:
            raise ValidationError(
                "Vote elector and proposal do not match."
            )

        if self.elector.user_id != self.cast_by_id:
            raise ValidationError(
                "Votes must be cast by the snapshotted elector."
            )

    def __str__(self):
        return f"{self.proposal_id}:{self.elector_id}:{self.choice}"


class OrganizationGovernanceVoteRevision(models.Model):
    id = models.BigAutoField(primary_key=True)

    vote = models.ForeignKey(
        OrganizationGovernanceVote,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    previous_choice = models.CharField(
        max_length=20,
        choices=OrganizationGovernanceVoteChoice.choices,
        null=True,
        blank=True,
    )
    new_choice = models.CharField(
        max_length=20,
        choices=OrganizationGovernanceVoteChoice.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_governance_vote_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Organization Governance Vote Revision"
        verbose_name_plural = "Organization Governance Vote Revisions"
        ordering = ("created_at", "id")

    def clean(self):
        super().clean()

        if self.vote.cast_by_id != self.actor_id:
            raise ValidationError(
                "Vote revisions must be recorded for the voting elector."
            )

    def __str__(self):
        return f"{self.vote_id}:{self.previous_choice}->{self.new_choice}"


class OrganizationGovernanceDecision(models.Model):
    id = models.BigAutoField(primary_key=True)

    proposal = models.OneToOneField(
        OrganizationGovernanceProposal,
        on_delete=models.CASCADE,
        related_name="decision",
    )
    result = models.CharField(
        max_length=30,
        choices=OrganizationGovernanceDecisionResult.choices,
        db_index=True,
    )

    eligible_count = models.PositiveIntegerField(default=0)
    participating_count = models.PositiveIntegerField(default=0)
    approve_count = models.PositiveIntegerField(default=0)
    reject_count = models.PositiveIntegerField(default=0)
    abstain_count = models.PositiveIntegerField(default=0)

    eligible_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")
    participating_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")
    approve_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")
    reject_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")
    abstain_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")
    quorum_required_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")
    approval_required_weight = models.DecimalField(max_digits=14, decimal_places=3, default="0.000")

    quorum_percent_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    approval_percent_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    participation_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="0.00",
    )
    approval_percent_actual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="0.00",
    )
    quorum_met = models.BooleanField(default=False)
    approval_met = models.BooleanField(default=False)

    algorithm_version = models.PositiveSmallIntegerField(default=1)
    decided_at = models.DateTimeField(default=timezone.now, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Organization Governance Decision"
        verbose_name_plural = "Organization Governance Decisions"

    def __str__(self):
        return f"{self.proposal_id}:{self.result}"
