# apps/organizations/admin/governance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationGovernanceDecision,
    OrganizationGovernanceElector,
    OrganizationGovernanceProposal,
    OrganizationGovernanceRule,
    OrganizationGovernanceVote,
    OrganizationGovernanceVoteRevision,
)


@admin.register(OrganizationGovernanceRule)
class OrganizationGovernanceRuleAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "action_key",
        "electorate_type",
        "quorum_percent",
        "approval_percent",
        "is_active",
    )
    list_filter = ("action_key", "electorate_type", "is_active")
    search_fields = ("organization__name", "organization__slug")


@admin.register(OrganizationGovernanceProposal)
class OrganizationGovernanceProposalAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "action_key",
        "status",
        "opened_at",
        "closes_at",
        "created_at",
    )
    list_filter = ("action_key", "status")
    search_fields = (
        "public_id",
        "organization__name",
        "title",
    )
    readonly_fields = (
        "public_id",
        "open_slot",
        "subject_key",
        "rule_snapshot",
        "proposed_by_membership",
        "created_by",
        "opened_at",
        "closes_at",
        "decided_at",
        "executed_at",
        "execution_error",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationGovernanceElector)
class OrganizationGovernanceElectorAdmin(admin.ModelAdmin):
    list_display = (
        "proposal",
        "membership",
        "user",
        "vote_weight",
        "is_eligible",
        "created_at",
    )
    list_filter = ("is_eligible",)
    search_fields = ("proposal__public_id", "user__email")
    readonly_fields = (
        "proposal",
        "membership",
        "user",
        "membership_id_snapshot",
        "role_keys_snapshot",
        "vote_weight",
        "is_eligible",
        "created_at",
    )


@admin.register(OrganizationGovernanceVote)
class OrganizationGovernanceVoteAdmin(admin.ModelAdmin):
    list_display = ("proposal", "cast_by", "choice", "cast_at")
    list_filter = ("choice",)
    search_fields = ("proposal__public_id", "cast_by__email")
    readonly_fields = (
        "public_id",
        "proposal",
        "elector",
        "choice",
        "cast_by",
        "cast_at",
        "updated_at",
    )


@admin.register(OrganizationGovernanceVoteRevision)
class OrganizationGovernanceVoteRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "vote",
        "previous_choice",
        "new_choice",
        "actor",
        "created_at",
    )
    list_filter = ("new_choice",)
    search_fields = (
        "vote__proposal__public_id",
        "actor__email",
    )
    readonly_fields = (
        "vote",
        "previous_choice",
        "new_choice",
        "actor",
        "created_at",
    )


@admin.register(OrganizationGovernanceDecision)
class OrganizationGovernanceDecisionAdmin(admin.ModelAdmin):
    list_display = (
        "proposal",
        "result",
        "eligible_count",
        "participating_count",
        "participation_percent",
        "approval_percent_actual",
        "quorum_met",
        "approval_met",
        "decided_at",
    )
    list_filter = ("result", "quorum_met", "approval_met")
    search_fields = (
        "proposal__public_id",
        "proposal__organization__name",
    )
    readonly_fields = (
        "proposal",
        "result",
        "eligible_count",
        "participating_count",
        "approve_count",
        "reject_count",
        "abstain_count",
        "eligible_weight",
        "participating_weight",
        "approve_weight",
        "reject_weight",
        "abstain_weight",
        "quorum_required_weight",
        "approval_required_weight",
        "quorum_percent_snapshot",
        "approval_percent_snapshot",
        "participation_percent",
        "approval_percent_actual",
        "quorum_met",
        "approval_met",
        "algorithm_version",
        "decided_at",
        "metadata",
    )
