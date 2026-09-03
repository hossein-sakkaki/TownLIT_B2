# apps/organizations/serializers/governance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from rest_framework import serializers

from apps.organizations.constants import (
    OrganizationGovernanceAction,
    OrganizationGovernanceVoteChoice,
)
from apps.organizations.models import (
    OrganizationGovernanceDecision,
    OrganizationGovernanceProposal,
    OrganizationGovernanceRule,
)


class OrganizationGovernanceRuleSerializer(serializers.ModelSerializer):
    electorate_role_key = serializers.CharField(
        source="electorate_role.key",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = OrganizationGovernanceRule
        fields = [
            "action_key",
            "electorate_type",
            "electorate_role_key",
            "quorum_percent",
            "approval_percent",
            "minimum_electors",
            "voting_period_hours",
            "allow_abstain",
            "allow_vote_changes",
            "exclude_target_membership",
            "is_active",
        ]
        read_only_fields = fields


class OrganizationGovernanceDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationGovernanceDecision
        fields = [
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
        ]
        read_only_fields = fields


class OrganizationGovernanceProposalSerializer(serializers.ModelSerializer):
    target_membership_public_id = serializers.UUIDField(
        source="target_membership.public_id",
        read_only=True,
        allow_null=True,
    )
    relationship_public_id = serializers.UUIDField(
        source="relationship.public_id",
        read_only=True,
        allow_null=True,
    )
    viewer_is_elector = serializers.SerializerMethodField()
    viewer_vote = serializers.SerializerMethodField()
    eligible_count = serializers.SerializerMethodField()
    votes_cast = serializers.SerializerMethodField()
    decision = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationGovernanceProposal
        fields = [
            "public_id",
            "action_key",
            "status",
            "title",
            "rationale",
            "target_membership_public_id",
            "relationship_public_id",
            "payload",
            "rule_snapshot",
            "viewer_is_elector",
            "viewer_vote",
            "eligible_count",
            "votes_cast",
            "opened_at",
            "closes_at",
            "decided_at",
            "executed_at",
            "execution_error",
            "decision",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _viewer_elector(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            return None

        return obj.electors.filter(
            user=user,
            is_eligible=True,
        ).first()

    def get_viewer_is_elector(self, obj):
        return self._viewer_elector(obj) is not None

    def get_viewer_vote(self, obj):
        elector = self._viewer_elector(obj)
        if not elector:
            return None

        vote = getattr(elector, "vote", None)
        return vote.choice if vote else None

    def get_eligible_count(self, obj):
        return obj.electors.filter(is_eligible=True).count()

    def get_votes_cast(self, obj):
        return obj.votes.filter(elector__is_eligible=True).count()

    def get_decision(self, obj):
        decision = getattr(obj, "decision", None)
        if not decision:
            return None

        return OrganizationGovernanceDecisionSerializer(decision).data


class OrganizationGovernanceProposalCreateSerializer(serializers.Serializer):
    action_key = serializers.ChoiceField(
        choices=OrganizationGovernanceAction.choices,
    )
    title = serializers.CharField(max_length=240)
    rationale = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    target_membership_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    relationship_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    payload = serializers.JSONField(required=False)
    open_immediately = serializers.BooleanField(default=False)


class OrganizationGovernanceVoteSerializer(serializers.Serializer):
    choice = serializers.ChoiceField(
        choices=OrganizationGovernanceVoteChoice.choices,
    )
