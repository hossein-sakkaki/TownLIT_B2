# apps/organizations/serializers/administration.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMiniSerializer
from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
)
from apps.organizations.models import Organization, OrganizationAuditLog


ORGANIZATION_AUDIT_CATEGORY_DEFINITIONS = (
    (
        "organization",
        "Organization",
        {
            OrganizationAuditAction.ORGANIZATION_CREATED,
            OrganizationAuditAction.ORGANIZATION_UPDATED,
        },
    ),
    (
        "membership",
        "Members",
        {
            OrganizationAuditAction.MEMBERSHIP_REQUESTED,
            OrganizationAuditAction.MEMBERSHIP_INVITED,
            OrganizationAuditAction.MEMBERSHIP_ACCEPTED,
            OrganizationAuditAction.MEMBERSHIP_REJECTED,
            OrganizationAuditAction.MEMBERSHIP_WITHDRAWN,
            OrganizationAuditAction.MEMBERSHIP_CANCELED,
            OrganizationAuditAction.MEMBER_LEFT,
            OrganizationAuditAction.MEMBER_REMOVED,
        },
    ),
    (
        "access",
        "Roles & Access",
        {
            OrganizationAuditAction.ROLE_ASSIGNED,
            OrganizationAuditAction.ROLE_REVOKED,
        },
    ),
    (
        "services",
        "Services & Modules",
        {
            OrganizationAuditAction.MODULE_ENABLED,
            OrganizationAuditAction.MODULE_DISABLED,
            OrganizationAuditAction.MODULE_SUSPENDED,
            OrganizationAuditAction.MODULE_RESTORED,
            OrganizationAuditAction.MODULE_UPDATED,
        },
    ),
    (
        "verification",
        "Verification",
        {
            OrganizationAuditAction.VERIFICATION_CASE_CREATED,
            OrganizationAuditAction.VERIFICATION_SUBMITTED,
            OrganizationAuditAction.VERIFICATION_NEEDS_INFORMATION,
            OrganizationAuditAction.VERIFICATION_APPROVED,
            OrganizationAuditAction.VERIFICATION_REJECTED,
            OrganizationAuditAction.VERIFICATION_WITHDRAWN,
            OrganizationAuditAction.VERIFICATION_REVOKED,
        },
    ),
    (
        "relationships",
        "Relationships",
        {
            OrganizationAuditAction.RELATIONSHIP_REQUESTED,
            OrganizationAuditAction.RELATIONSHIP_CONSENT_APPROVED,
            OrganizationAuditAction.RELATIONSHIP_CONSENT_REJECTED,
            OrganizationAuditAction.RELATIONSHIP_ACTIVATED,
            OrganizationAuditAction.RELATIONSHIP_ENDED,
        },
    ),
    (
        "governance",
        "Governance",
        {
            OrganizationAuditAction.GOVERNANCE_PROPOSAL_CREATED,
            OrganizationAuditAction.GOVERNANCE_PROPOSAL_OPENED,
            OrganizationAuditAction.GOVERNANCE_DECIDED,
            OrganizationAuditAction.GOVERNANCE_EXECUTED,
            OrganizationAuditAction.GOVERNANCE_EXECUTION_FAILED,
        },
    ),
)

ORGANIZATION_AUDIT_CATEGORY_ACTIONS = {
    key: frozenset(actions)
    for key, _, actions in ORGANIZATION_AUDIT_CATEGORY_DEFINITIONS
}

CLIENT_VISIBLE_ORGANIZATION_AUDIT_ACTIONS = frozenset(
    action
    for _, _, actions in ORGANIZATION_AUDIT_CATEGORY_DEFINITIONS
    for action in actions
)


def organization_audit_category_for_action(action):
    for key, _, actions in ORGANIZATION_AUDIT_CATEGORY_DEFINITIONS:
        if action in actions:
            return key
    return "organization"


def organization_audit_category_choices():
    return [
        {
            "key": key,
            "label": label,
        }
        for key, label, _ in ORGANIZATION_AUDIT_CATEGORY_DEFINITIONS
    ]


def organization_audit_source_choices():
    return [
        {
            "key": value,
            "label": label,
        }
        for value, label in OrganizationAuditSource.choices
    ]


class OrganizationAdministrationOverviewSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Organization
        fields = [
            "public_id",
            "name",
            "slug",
            "status",
            "status_label",
            "created_at",
            "updated_at",
            "suspended_at",
            "closed_at",
        ]
        read_only_fields = fields


class OrganizationAuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(
        source="get_action_display",
        read_only=True,
    )
    source_label = serializers.CharField(
        source="get_source_display",
        read_only=True,
    )
    category = serializers.SerializerMethodField()
    actor = serializers.SerializerMethodField()
    actor_label = serializers.SerializerMethodField()
    target_user = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationAuditLog
        fields = [
            "id",
            "action",
            "action_label",
            "category",
            "source",
            "source_label",
            "actor",
            "actor_label",
            "target_user",
            "target_label",
            "reference",
            "created_at",
        ]
        read_only_fields = fields

    def get_category(self, obj):
        return organization_audit_category_for_action(obj.action)

    def get_actor(self, obj):
        if obj.source in {
            OrganizationAuditSource.ADMIN,
            OrganizationAuditSource.SYSTEM,
        } or (
            obj.actor_id
            and getattr(obj.actor, "is_staff", False)
        ):
            return None

        if not obj.actor_id:
            return None

        return UserMiniSerializer(
            obj.actor,
            context=self.context,
        ).data

    def get_actor_label(self, obj):
        if obj.source in {
            OrganizationAuditSource.ADMIN,
            OrganizationAuditSource.SYSTEM,
        } or (
            obj.actor_id
            and getattr(obj.actor, "is_staff", False)
        ):
            return "TownLIT"

        if obj.actor_id:
            return self._user_label(obj.actor)

        if obj.source == OrganizationAuditSource.GOVERNANCE:
            return "Organization Governance"

        return "TownLIT"

    def get_target_user(self, obj):
        if not obj.target_user_id:
            return None

        return UserMiniSerializer(
            obj.target_user,
            context=self.context,
        ).data

    def get_target_label(self, obj):
        if obj.target_user_id:
            return self._user_label(obj.target_user)

        member_user = self._member_user_for_log(obj)
        if member_user:
            return self._user_label(member_user)

        return None

    def get_reference(self, obj):
        if obj.governance_proposal_id:
            proposal = obj.governance_proposal
            return {
                "kind": "governance_proposal",
                "id": str(proposal.public_id),
                "label": proposal.title,
                "detail": proposal.action_key,
            }

        if obj.relationship_id:
            relationship = obj.relationship
            label = (
                f"{relationship.source_organization.name} → "
                f"{relationship.target_organization.name}"
            )
            return {
                "kind": "relationship",
                "id": str(relationship.public_id),
                "label": label,
                "detail": relationship.relationship_type,
            }

        if obj.verification_case_id:
            verification_case = obj.verification_case
            return {
                "kind": "verification_case",
                "id": str(verification_case.public_id),
                "label": verification_case.get_path_display(),
                "detail": verification_case.status,
            }

        if obj.module_activation_id:
            activation = obj.module_activation
            label = activation.display_name or activation.module.name
            return {
                "kind": "module_activation",
                "id": str(activation.public_id),
                "label": label,
                "detail": activation.module.key,
            }

        if obj.role_assignment_id:
            assignment = obj.role_assignment
            member_user = assignment.membership.member.user
            return {
                "kind": "role_assignment",
                "id": str(assignment.public_id),
                "label": assignment.role.name,
                "detail": self._user_label(member_user),
            }

        if obj.membership_request_id:
            membership_request = obj.membership_request
            return {
                "kind": "membership_request",
                "id": str(membership_request.public_id),
                "label": self._user_label(membership_request.member.user),
                "detail": membership_request.direction,
            }

        if obj.membership_id:
            membership = obj.membership
            return {
                "kind": "membership",
                "id": str(membership.public_id),
                "label": self._user_label(membership.member.user),
                "detail": membership.status,
            }

        if obj.target_user_id:
            return {
                "kind": "user",
                "id": str(obj.target_user_id),
                "label": self._user_label(obj.target_user),
                "detail": None,
            }

        return None

    def _member_user_for_log(self, obj):
        if obj.membership_id:
            return obj.membership.member.user

        if obj.membership_request_id:
            return obj.membership_request.member.user

        if obj.role_assignment_id:
            return obj.role_assignment.membership.member.user

        return None

    @staticmethod
    def _user_label(user):
        if not user:
            return "TownLIT Member"

        parts = [
            str(getattr(user, "name", "") or "").strip(),
            str(getattr(user, "family", "") or "").strip(),
        ]
        full_name = " ".join(part for part in parts if part).strip()

        if full_name:
            return full_name

        username = str(getattr(user, "username", "") or "").strip()
        if username:
            return f"@{username}"

        return "TownLIT Member"
