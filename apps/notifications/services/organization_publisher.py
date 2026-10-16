# apps/notifications/services/organization_publisher.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from __future__ import annotations

import logging

from apps.notifications.services.organization_audience import (
    user_has_active_organization_membership,
    users_with_organization_permission,
)
from apps.notifications.services.organization_presentation import (
    organization_audit_copy,
    subscription_event_copy,
)
from apps.notifications.services.services import (
    create_and_dispatch_notification,
)
from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationPermissionKey,
    OrganizationRoleScope,
)
from apps.organizations.models import OrganizationAuditLog
from apps.subscriptions.models import SubscriptionEvent


logger = logging.getLogger(__name__)


AUDIT_NOTIFICATION_TYPES = {
    OrganizationAuditAction.MEMBERSHIP_REQUESTED: "organization_membership_requested",
    OrganizationAuditAction.MEMBERSHIP_INVITED: "organization_membership_invited",
    OrganizationAuditAction.MEMBERSHIP_ACCEPTED: "organization_membership_accepted",
    OrganizationAuditAction.MEMBERSHIP_REJECTED: "organization_membership_rejected",
    OrganizationAuditAction.MEMBERSHIP_WITHDRAWN: "organization_membership_withdrawn",
    OrganizationAuditAction.MEMBERSHIP_CANCELED: "organization_membership_canceled",
    OrganizationAuditAction.MEMBER_LEFT: "organization_member_left",
    OrganizationAuditAction.MEMBER_REMOVED: "organization_member_removed",
    OrganizationAuditAction.ROLE_ASSIGNED: "organization_role_assigned",
    OrganizationAuditAction.ROLE_REVOKED: "organization_role_revoked",
    OrganizationAuditAction.MODULE_ENABLED: "organization_module_enabled",
    OrganizationAuditAction.MODULE_DISABLED: "organization_module_disabled",
    OrganizationAuditAction.MODULE_SUSPENDED: "organization_module_suspended",
    OrganizationAuditAction.MODULE_RESTORED: "organization_module_restored",
    OrganizationAuditAction.MODULE_UPDATED: "organization_module_updated",
    OrganizationAuditAction.VERIFICATION_NEEDS_INFORMATION: "organization_verification_needs_information",
    OrganizationAuditAction.VERIFICATION_APPROVED: "organization_verification_approved",
    OrganizationAuditAction.VERIFICATION_REJECTED: "organization_verification_rejected",
    OrganizationAuditAction.VERIFICATION_REVOKED: "organization_verification_revoked",
    OrganizationAuditAction.RELATIONSHIP_REQUESTED: "organization_relationship_requested",
    OrganizationAuditAction.RELATIONSHIP_CONSENT_APPROVED: "organization_relationship_consent_approved",
    OrganizationAuditAction.RELATIONSHIP_CONSENT_REJECTED: "organization_relationship_consent_rejected",
    OrganizationAuditAction.RELATIONSHIP_ACTIVATED: "organization_relationship_activated",
    OrganizationAuditAction.RELATIONSHIP_ENDED: "organization_relationship_ended",
    OrganizationAuditAction.GOVERNANCE_PROPOSAL_OPENED: "organization_governance_opened",
    OrganizationAuditAction.GOVERNANCE_DECIDED: "organization_governance_decided",
    OrganizationAuditAction.GOVERNANCE_EXECUTION_FAILED: "organization_governance_execution_failed",
}


AUDIT_PERMISSION_MAP = {
    OrganizationAuditAction.MEMBERSHIP_REQUESTED: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.MEMBERSHIP_ACCEPTED: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.MEMBERSHIP_REJECTED: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.MEMBERSHIP_WITHDRAWN: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.MEMBERSHIP_CANCELED: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.MEMBER_LEFT: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.MEMBER_REMOVED: OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationAuditAction.ROLE_ASSIGNED: OrganizationPermissionKey.MANAGE_ROLES,
    OrganizationAuditAction.ROLE_REVOKED: OrganizationPermissionKey.MANAGE_ROLES,
    OrganizationAuditAction.MODULE_ENABLED: OrganizationPermissionKey.MANAGE_MODULES,
    OrganizationAuditAction.MODULE_DISABLED: OrganizationPermissionKey.MANAGE_MODULES,
    OrganizationAuditAction.MODULE_SUSPENDED: OrganizationPermissionKey.MANAGE_MODULES,
    OrganizationAuditAction.MODULE_RESTORED: OrganizationPermissionKey.MANAGE_MODULES,
    OrganizationAuditAction.MODULE_UPDATED: OrganizationPermissionKey.MANAGE_MODULES,
    OrganizationAuditAction.VERIFICATION_NEEDS_INFORMATION: OrganizationPermissionKey.MANAGE_VERIFICATION,
    OrganizationAuditAction.VERIFICATION_APPROVED: OrganizationPermissionKey.MANAGE_VERIFICATION,
    OrganizationAuditAction.VERIFICATION_REJECTED: OrganizationPermissionKey.MANAGE_VERIFICATION,
    OrganizationAuditAction.VERIFICATION_REVOKED: OrganizationPermissionKey.MANAGE_VERIFICATION,
    OrganizationAuditAction.RELATIONSHIP_REQUESTED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationAuditAction.RELATIONSHIP_CONSENT_APPROVED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationAuditAction.RELATIONSHIP_CONSENT_REJECTED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationAuditAction.RELATIONSHIP_ACTIVATED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationAuditAction.RELATIONSHIP_ENDED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationAuditAction.GOVERNANCE_DECIDED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationAuditAction.GOVERNANCE_EXECUTION_FAILED: OrganizationPermissionKey.MANAGE_GOVERNANCE,
}


def _organization_link(organization) -> str:
    return str(getattr(organization, "share_url", "") or organization.get_absolute_url())


def _audit_metadata(audit_log) -> dict:
    return {
        "source": "organization_audit",
        "organization_public_id": str(audit_log.organization.public_id),
        "organization_slug": audit_log.organization.slug,
        "audit_log_id": audit_log.id,
        "audit_action": audit_log.action,
        "membership_public_id": str(audit_log.membership.public_id) if audit_log.membership_id else "",
        "membership_request_public_id": str(audit_log.membership_request.public_id) if audit_log.membership_request_id else "",
        "role_assignment_public_id": str(audit_log.role_assignment.public_id) if audit_log.role_assignment_id else "",
        "verification_case_public_id": str(audit_log.verification_case.public_id) if audit_log.verification_case_id else "",
        "relationship_public_id": str(audit_log.relationship.public_id) if audit_log.relationship_id else "",
        "governance_proposal_public_id": str(audit_log.governance_proposal.public_id) if audit_log.governance_proposal_id else "",
        "module_activation_public_id": str(audit_log.module_activation.public_id) if audit_log.module_activation_id else "",
    }


def _send(
    *,
    recipient,
    audit_log,
    notif_type,
    title,
    message,
    organization_context,
):
    metadata = _audit_metadata(audit_log)

    create_and_dispatch_notification(
        recipient=recipient,
        actor=audit_log.actor,
        notif_type=notif_type,
        title=title,
        message=message,
        target_obj=audit_log.organization,
        action_obj=audit_log,
        link=_organization_link(audit_log.organization),
        metadata=metadata,
        extra_payload=metadata,
        organization_context=organization_context,
        respect_relationship_policy=False,
    )


def _notify_direct_target(audit_log, notif_type, title, message):
    target_user = audit_log.target_user
    if target_user is None:
        return

    organization_context = None

    if audit_log.action in {
        OrganizationAuditAction.ROLE_ASSIGNED,
        OrganizationAuditAction.ROLE_REVOKED,
    } and user_has_active_organization_membership(
        organization=audit_log.organization,
        user=target_user,
    ):
        organization_context = audit_log.organization

    _send(
        recipient=target_user,
        audit_log=audit_log,
        notif_type=notif_type,
        title=title,
        message=message,
        organization_context=organization_context,
    )


def publish_organization_audit_notification(*, audit_log_id: int) -> int:
    audit_log = (
        OrganizationAuditLog.objects
        .select_related(
            "organization",
            "actor",
            "target_user",
            "membership",
            "membership_request",
            "role_assignment",
            "verification_case",
            "relationship",
            "governance_proposal",
            "module_activation__module",
        )
        .filter(pk=audit_log_id)
        .first()
    )

    if audit_log is None:
        return 0

    notif_type = AUDIT_NOTIFICATION_TYPES.get(audit_log.action)
    if not notif_type:
        return 0

    title, message = organization_audit_copy(audit_log)
    sent_user_ids = set()

    direct_target_actions = {
        OrganizationAuditAction.MEMBERSHIP_INVITED,
        OrganizationAuditAction.MEMBERSHIP_ACCEPTED,
        OrganizationAuditAction.MEMBERSHIP_REJECTED,
        OrganizationAuditAction.MEMBERSHIP_CANCELED,
        OrganizationAuditAction.MEMBER_REMOVED,
        OrganizationAuditAction.ROLE_ASSIGNED,
        OrganizationAuditAction.ROLE_REVOKED,
    }

    if audit_log.action in direct_target_actions and audit_log.target_user_id:
        _notify_direct_target(audit_log, notif_type, title, message)
        sent_user_ids.add(audit_log.target_user_id)

    if (
        audit_log.action == OrganizationAuditAction.GOVERNANCE_PROPOSAL_OPENED
        and audit_log.governance_proposal_id
    ):
        users = (
            audit_log.governance_proposal.electors
            .filter(is_eligible=True)
            .select_related("user")
        )
        recipients = [elector.user for elector in users if elector.user_id]
    else:
        permission_key = AUDIT_PERMISSION_MAP.get(audit_log.action)
        if not permission_key:
            return len(sent_user_ids)

        scope_type = OrganizationRoleScope.ORGANIZATION
        scope_key = ""

        if audit_log.module_activation_id:
            scope_type = OrganizationRoleScope.MODULE
            scope_key = audit_log.module_activation.module.key

        recipients = users_with_organization_permission(
            organization=audit_log.organization,
            permission_key=permission_key,
            scope_type=scope_type,
            scope_key=scope_key,
        )

    for recipient in recipients:
        if recipient.id in sent_user_ids:
            continue

        _send(
            recipient=recipient,
            audit_log=audit_log,
            notif_type=notif_type,
            title=title,
            message=message,
            organization_context=audit_log.organization,
        )
        sent_user_ids.add(recipient.id)

    return len(sent_user_ids)


def publish_subscription_event_notification(*, event_id: int) -> int:
    event = (
        SubscriptionEvent.objects
        .select_related("account", "actor", "subscription")
        .filter(pk=event_id)
        .first()
    )
    if event is None:
        return 0

    try:
        organization = event.account.organization
    except Exception:
        return 0

    notif_type, title, message = subscription_event_copy(event, organization)
    if not notif_type:
        return 0

    recipients = users_with_organization_permission(
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_BILLING,
    )
    metadata = {
        "source": "subscription_event",
        "organization_public_id": str(organization.public_id),
        "organization_slug": organization.slug,
        "subscription_event_id": event.id,
        "subscription_event_type": event.event_type,
        "subscription_public_id": (
            str(event.subscription.public_id)
            if event.subscription_id
            else ""
        ),
    }
    count = 0
    for recipient in recipients:
        create_and_dispatch_notification(
            recipient=recipient,
            actor=event.actor,
            notif_type=notif_type,
            title=title,
            message=message,
            target_obj=organization,
            action_obj=event,
            link=_organization_link(organization),
            metadata=metadata,
            extra_payload=metadata,
            organization_context=organization,
            respect_relationship_policy=False,
        )
        count += 1
    return count
