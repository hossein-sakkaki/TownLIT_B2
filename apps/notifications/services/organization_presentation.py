# apps/notifications/services/organization_presentation.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from __future__ import annotations


def _display_name(user) -> str:
    if user is None:
        return "A member"

    name = " ".join(
        part.strip()
        for part in (
            str(getattr(user, "name", "") or ""),
            str(getattr(user, "family", "") or ""),
        )
        if part and part.strip()
    )
    return name or str(getattr(user, "username", "") or "A member")


def organization_audit_copy(audit_log) -> tuple[str, str]:
    organization_name = audit_log.organization.name
    person = _display_name(audit_log.target_user or audit_log.actor)
    action = audit_log.action

    copy = {
        "membership_requested": (
            "New membership request",
            f"{person} requested to join {organization_name}.",
        ),
        "membership_invited": (
            "Organization invitation",
            f"You were invited to join {organization_name}.",
        ),
        "membership_accepted": (
            "Membership accepted",
            f"{person}'s membership in {organization_name} was accepted.",
        ),
        "membership_rejected": (
            "Membership request declined",
            f"{person}'s membership request for {organization_name} was declined.",
        ),
        "membership_withdrawn": (
            "Membership request withdrawn",
            f"{person} withdrew a membership request for {organization_name}.",
        ),
        "membership_canceled": (
            "Organization invitation canceled",
            f"An invitation to join {organization_name} was canceled.",
        ),
        "member_left": (
            "Organization member left",
            f"{person} left {organization_name}.",
        ),
        "member_removed": (
            "Organization membership ended",
            f"{person} was removed from {organization_name}.",
        ),
        "role_assigned": (
            "Organization role assigned",
            f"A role was assigned to {person} in {organization_name}.",
        ),
        "role_revoked": (
            "Organization role changed",
            f"A role was revoked from {person} in {organization_name}.",
        ),
        "module_enabled": (
            "Organization service enabled",
            f"A service was enabled for {organization_name}.",
        ),
        "module_disabled": (
            "Organization service disabled",
            f"A service was disabled for {organization_name}.",
        ),
        "module_suspended": (
            "Organization service suspended",
            f"A service was suspended for {organization_name}.",
        ),
        "module_restored": (
            "Organization service restored",
            f"A service was restored for {organization_name}.",
        ),
        "module_updated": (
            "Organization service updated",
            f"A service configuration changed for {organization_name}.",
        ),
        "verification_needs_information": (
            "Verification needs information",
            f"{organization_name} verification needs additional information.",
        ),
        "verification_approved": (
            "Organization verified",
            f"{organization_name} verification was approved.",
        ),
        "verification_rejected": (
            "Verification not approved",
            f"{organization_name} verification was not approved.",
        ),
        "verification_revoked": (
            "Organization verification revoked",
            f"{organization_name} verification was revoked.",
        ),
        "relationship_requested": (
            "Organization relationship request",
            f"{organization_name} has a new organization relationship request.",
        ),
        "relationship_consent_approved": (
            "Organization relationship approved",
            f"An organization relationship was approved for {organization_name}.",
        ),
        "relationship_consent_rejected": (
            "Organization relationship declined",
            f"An organization relationship was declined for {organization_name}.",
        ),
        "relationship_activated": (
            "Organization relationship active",
            f"An organization relationship is now active for {organization_name}.",
        ),
        "relationship_ended": (
            "Organization relationship ended",
            f"An organization relationship ended for {organization_name}.",
        ),
        "governance_proposal_opened": (
            "Governance action requires attention",
            f"A governance proposal is open in {organization_name}.",
        ),
        "governance_decided": (
            "Governance decision recorded",
            f"A governance decision was recorded in {organization_name}.",
        ),
        "governance_execution_failed": (
            "Governance action failed",
            f"An approved governance action could not be completed in {organization_name}.",
        ),
    }

    return copy.get(
        action,
        (
            "Organization update",
            f"There is an update for {organization_name}.",
        ),
    )


def subscription_event_copy(event, organization) -> tuple[str, str, str]:
    mapping = {
        "trial_started": (
            "organization_subscription_trial_started",
            "Organization trial started",
            f"A subscription trial started for {organization.name}.",
        ),
        "subscription_activated": (
            "organization_subscription_activated",
            "Organization subscription active",
            f"The subscription for {organization.name} is active.",
        ),
        "billing_profile_updated": (
            "organization_billing_profile_updated",
            "Organization billing updated",
            f"Billing information was updated for {organization.name}.",
        ),
    }
    return mapping.get(event.event_type, ("", "", ""))
