# apps/organizations/constants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.db import models


class OrganizationKind(models.TextChoices):
    CHURCH = "church", "Church"
    MINISTRY = "ministry", "Ministry"
    MISSION = "mission", "Mission Organization"
    NONPROFIT = "nonprofit", "Nonprofit Organization"
    EDUCATIONAL_INSTITUTION = "educational_institution", "Educational Institution"
    NETWORK = "network", "Network or Association"
    PUBLISHER = "publisher", "Publisher or Media Organization"
    COMMUNITY = "community", "Community Organization"
    OTHER = "other", "Other"


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    CLOSED = "closed", "Closed"


class OrganizationVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    UNLISTED = "unlisted", "Unlisted"
    PRIVATE = "private", "Private"


class OrganizationConnectionType(models.TextChoices):
    FOLLOWER = "follower", "Follower"
    MEMBER = "member", "Member"


class OrganizationConnectionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class MembershipRequestDirection(models.TextChoices):
    MEMBER_TO_ORGANIZATION = "member_to_organization", "Member to Organization"
    ORGANIZATION_TO_MEMBER = "organization_to_member", "Organization to Member"


class MembershipRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"
    CANCELED = "canceled", "Canceled"
    EXPIRED = "expired", "Expired"


class OrganizationMembershipStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    ENDED = "ended", "Ended"


CURRENT_MEMBERSHIP_STATUSES = (
    OrganizationMembershipStatus.ACTIVE,
    OrganizationMembershipStatus.SUSPENDED,
)

# Membership states that may exercise organization permissions.
ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES = (
    OrganizationMembershipStatus.ACTIVE,
)


class OrganizationRoleScope(models.TextChoices):
    ORGANIZATION = "organization", "Organization"
    MODULE = "module", "Module"


class OrganizationRoleKey:
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    MEMBERSHIP_MANAGER = "membership_manager"
    CONTENT_MANAGER = "content_manager"
    BILLING_MANAGER = "billing_manager"
    VERIFICATION_MANAGER = "verification_manager"
    MODULE_MANAGER = "module_manager"


class OrganizationPermissionKey:
    VIEW_ADMIN = "organizations.admin.view"
    MANAGE_PROFILE = "organizations.profile.manage"
    MANAGE_MEMBERS = "organizations.members.manage"
    MANAGE_ROLES = "organizations.roles.manage"
    MANAGE_CONTENT = "organizations.content.manage"
    MANAGE_ANNOUNCEMENTS = "organizations.announcements.manage"
    MANAGE_MODULES = "organizations.modules.manage"
    MANAGE_BILLING = "organizations.billing.manage"
    MANAGE_VERIFICATION = "organizations.verification.manage"
    MANAGE_GOVERNANCE = "organizations.governance.manage"
    MANAGE_SETTINGS = "organizations.settings.manage"


DEFAULT_PERMISSION_DEFINITIONS = (
    (OrganizationPermissionKey.VIEW_ADMIN, "View Organization Admin", "administration"),
    (OrganizationPermissionKey.MANAGE_PROFILE, "Manage Organization Profile", "profile"),
    (OrganizationPermissionKey.MANAGE_MEMBERS, "Manage Organization Members", "membership"),
    (OrganizationPermissionKey.MANAGE_ROLES, "Manage Organization Roles", "access"),
    (OrganizationPermissionKey.MANAGE_CONTENT, "Manage Organization Content", "content"),
    (OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS, "Manage Organization Announcements", "content"),
    (OrganizationPermissionKey.MANAGE_MODULES, "Manage Organization Modules", "modules"),
    (OrganizationPermissionKey.MANAGE_BILLING, "Manage Organization Billing", "billing"),
    (OrganizationPermissionKey.MANAGE_VERIFICATION, "Manage Organization Verification", "verification"),
    (OrganizationPermissionKey.MANAGE_GOVERNANCE, "Manage Organization Governance", "governance"),
    (OrganizationPermissionKey.MANAGE_SETTINGS, "Manage Organization Settings", "administration"),
)


DEFAULT_ROLE_DEFINITIONS = (
    {
        "key": OrganizationRoleKey.OWNER,
        "name": "Owner",
        "description": "Protected organization ownership role.",
        "priority": 1000,
        "is_protected": True,
        "permissions": tuple(key for key, _, _ in DEFAULT_PERMISSION_DEFINITIONS),
    },
    {
        "key": OrganizationRoleKey.ADMINISTRATOR,
        "name": "Administrator",
        "description": "General organization administration role.",
        "priority": 800,
        "is_protected": False,
        "permissions": (
            OrganizationPermissionKey.VIEW_ADMIN,
            OrganizationPermissionKey.MANAGE_PROFILE,
            OrganizationPermissionKey.MANAGE_MEMBERS,
            OrganizationPermissionKey.MANAGE_ROLES,
            OrganizationPermissionKey.MANAGE_CONTENT,
            OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS,
            OrganizationPermissionKey.MANAGE_MODULES,
            OrganizationPermissionKey.MANAGE_SETTINGS,
        ),
    },
    {
        "key": OrganizationRoleKey.MEMBERSHIP_MANAGER,
        "name": "Membership Manager",
        "description": "Manages organization membership workflows.",
        "priority": 500,
        "is_protected": False,
        "permissions": (
            OrganizationPermissionKey.VIEW_ADMIN,
            OrganizationPermissionKey.MANAGE_MEMBERS,
        ),
    },
    {
        "key": OrganizationRoleKey.CONTENT_MANAGER,
        "name": "Content Manager",
        "description": "Manages organization content and announcements.",
        "priority": 500,
        "is_protected": False,
        "permissions": (
            OrganizationPermissionKey.VIEW_ADMIN,
            OrganizationPermissionKey.MANAGE_CONTENT,
            OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS,
        ),
    },
    {
        "key": OrganizationRoleKey.BILLING_MANAGER,
        "name": "Billing Manager",
        "description": "Manages organization billing and subscriptions.",
        "priority": 500,
        "is_protected": False,
        "permissions": (
            OrganizationPermissionKey.VIEW_ADMIN,
            OrganizationPermissionKey.MANAGE_BILLING,
        ),
    },
    {
        "key": OrganizationRoleKey.VERIFICATION_MANAGER,
        "name": "Verification Manager",
        "description": "Manages organization verification workflows.",
        "priority": 500,
        "is_protected": False,
        "permissions": (
            OrganizationPermissionKey.VIEW_ADMIN,
            OrganizationPermissionKey.MANAGE_VERIFICATION,
        ),
    },
    {
        "key": OrganizationRoleKey.MODULE_MANAGER,
        "name": "Module Manager",
        "description": "Manages an assigned organization service module.",
        "priority": 400,
        "is_protected": False,
        "permissions": (
            OrganizationPermissionKey.VIEW_ADMIN,
            OrganizationPermissionKey.MANAGE_MODULES,
        ),
    },
)


class OrganizationVerificationPath(models.TextChoices):
    DIRECT = "direct", "Direct Legal Verification"
    SPONSORED_BRANCH = "sponsored_branch", "Sponsored Branch Verification"


class OrganizationVerificationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under Review"
    NEEDS_INFORMATION = "needs_information", "Needs Information"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


OPEN_VERIFICATION_CASE_STATUSES = (
    OrganizationVerificationStatus.DRAFT,
    OrganizationVerificationStatus.SUBMITTED,
    OrganizationVerificationStatus.UNDER_REVIEW,
    OrganizationVerificationStatus.NEEDS_INFORMATION,
)


class OrganizationVerificationDocumentType(models.TextChoices):
    INCORPORATION = "incorporation", "Incorporation Document"
    CHARITY_REGISTRATION = "charity_registration", "Charity Registration"
    CHURCH_REGISTRATION = "church_registration", "Church Registration"
    TAX_DOCUMENT = "tax_document", "Tax Document"
    AUTHORIZATION_LETTER = "authorization_letter", "Authorization Letter"
    PARENT_ORGANIZATION_LETTER = "parent_organization_letter", "Parent Organization Letter"
    REPRESENTATIVE_IDENTITY = "representative_identity", "Authorized Representative Identity"
    OTHER = "other", "Other"


class OrganizationVerificationDocumentReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


class OrganizationVerificationGrantType(models.TextChoices):
    DIRECT = "direct", "Verified Organization"
    SPONSORED_BRANCH = "sponsored_branch", "Verified Branch"


class OrganizationVerificationGrantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUPERSEDED = "superseded", "Superseded"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class OrganizationRelationshipType(models.TextChoices):
    PARENT_BRANCH = "parent_branch", "Parent / Branch"
    AFFILIATE = "affiliate", "Affiliate"
    NETWORK_MEMBER = "network_member", "Network Membership"
    SPONSORSHIP = "sponsorship", "Sponsorship"


class OrganizationRelationshipStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"
    ENDED = "ended", "Ended"


CURRENT_RELATIONSHIP_STATUSES = (
    OrganizationRelationshipStatus.PENDING,
    OrganizationRelationshipStatus.ACTIVE,
    OrganizationRelationshipStatus.SUSPENDED,
)


class OrganizationRelationshipConsentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    REVOKED = "revoked", "Revoked"


class OrganizationGovernanceAction(models.TextChoices):
    OWNER_ADDITION = "owner_addition", "Add Owner"
    OWNER_REMOVAL = "owner_removal", "Remove Owner"
    ORGANIZATION_CLOSURE = "organization_closure", "Close Organization"
    ORGANIZATION_RESTORATION = "organization_restoration", "Restore Organization"
    RELATIONSHIP_CONSENT = "relationship_consent", "Relationship Consent"
    RELATIONSHIP_ENDING = "relationship_ending", "End Relationship"


class OrganizationGovernanceElectorateType(models.TextChoices):
    OWNERS = "owners", "Owners"
    ACTIVE_MEMBERS = "active_members", "Active Members"
    ROLE = "role", "Specific Role"


class OrganizationGovernanceProposalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELED = "canceled", "Canceled"
    EXECUTED = "executed", "Executed"
    EXECUTION_FAILED = "execution_failed", "Execution Failed"


class OrganizationGovernanceVoteChoice(models.TextChoices):
    APPROVE = "approve", "Approve"
    REJECT = "reject", "Reject"
    ABSTAIN = "abstain", "Abstain"


class OrganizationGovernanceDecisionResult(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    NO_QUORUM = "no_quorum", "No Quorum"
    INSUFFICIENT_ELECTORATE = "insufficient_electorate", "Insufficient Electorate"


DEFAULT_GOVERNANCE_RULES = (
    {
        "action_key": OrganizationGovernanceAction.OWNER_ADDITION,
        "electorate_type": OrganizationGovernanceElectorateType.OWNERS,
        "quorum_percent": "100.00",
        "approval_percent": "66.67",
        "minimum_electors": 1,
        "voting_period_hours": 72,
        "allow_abstain": True,
        "allow_vote_changes": False,
        "exclude_target_membership": False,
    },
    {
        "action_key": OrganizationGovernanceAction.OWNER_REMOVAL,
        "electorate_type": OrganizationGovernanceElectorateType.OWNERS,
        "quorum_percent": "100.00",
        "approval_percent": "66.67",
        "minimum_electors": 1,
        "voting_period_hours": 72,
        "allow_abstain": True,
        "allow_vote_changes": False,
        "exclude_target_membership": True,
    },
    {
        "action_key": OrganizationGovernanceAction.ORGANIZATION_CLOSURE,
        "electorate_type": OrganizationGovernanceElectorateType.OWNERS,
        "quorum_percent": "100.00",
        "approval_percent": "100.00",
        "minimum_electors": 1,
        "voting_period_hours": 120,
        "allow_abstain": True,
        "allow_vote_changes": False,
        "exclude_target_membership": False,
    },
    {
        "action_key": OrganizationGovernanceAction.ORGANIZATION_RESTORATION,
        "electorate_type": OrganizationGovernanceElectorateType.OWNERS,
        "quorum_percent": "100.00",
        "approval_percent": "100.00",
        "minimum_electors": 1,
        "voting_period_hours": 72,
        "allow_abstain": True,
        "allow_vote_changes": False,
        "exclude_target_membership": False,
    },
    {
        "action_key": OrganizationGovernanceAction.RELATIONSHIP_CONSENT,
        "electorate_type": OrganizationGovernanceElectorateType.OWNERS,
        "quorum_percent": "100.00",
        "approval_percent": "66.67",
        "minimum_electors": 1,
        "voting_period_hours": 72,
        "allow_abstain": True,
        "allow_vote_changes": False,
        "exclude_target_membership": False,
    },
    {
        "action_key": OrganizationGovernanceAction.RELATIONSHIP_ENDING,
        "electorate_type": OrganizationGovernanceElectorateType.OWNERS,
        "quorum_percent": "66.67",
        "approval_percent": "66.67",
        "minimum_electors": 1,
        "voting_period_hours": 72,
        "allow_abstain": True,
        "allow_vote_changes": False,
        "exclude_target_membership": False,
    },
)



class OrganizationModuleKey(models.TextChoices):
    CHURCH = "church", "Church & Congregational Life"
    MISSIONS = "missions", "Missions & Evangelism"
    EDUCATION = "education", "Education & Theological Training"
    COUNSELING = "counseling", "Counseling, Pastoral Care & Recovery"
    WORSHIP = "worship", "Worship, Music & Creative Arts"
    EVENTS = "events", "Events, Conferences & Retreats"
    CHILDREN_FAMILY = "children_family", "Children & Family Ministry"
    YOUTH_YOUNG_ADULTS = "youth_young_adults", "Youth & Young Adults"
    WOMEN = "women", "Women’s Ministry"
    MEN = "men", "Men’s Ministry"
    COMMUNITY_CARE = "community_care", "Community Care & Humanitarian Services"
    MEDIA_RESOURCES = "media_resources", "Media, Publishing & Resource Library"


class OrganizationModuleActivationStatus(models.TextChoices):
    ENABLED = "enabled", "Enabled"
    DISABLED = "disabled", "Disabled"
    SUSPENDED = "suspended", "Suspended by TownLIT"


class OrganizationModuleVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    MEMBERS_ONLY = "members_only", "Members Only"
    PRIVATE = "private", "Private"


class OrganizationModuleAccessMode(models.TextChoices):
    FULL = "full", "Full Access"
    READ_ONLY = "read_only", "Read Only"
    LOCKED = "locked", "Locked"
    UNAVAILABLE = "unavailable", "Unavailable"


class OrganizationModuleFallbackAccessMode(models.TextChoices):
    READ_ONLY = "read_only", "Read Only"
    LOCKED = "locked", "Locked"


class OrganizationModuleAccessReason(models.TextChoices):
    AVAILABLE = "available", "Available"
    FEATURE_DISABLED = "feature_disabled", "Feature Disabled"
    ORGANIZATION_UNAVAILABLE = "organization_unavailable", "Organization Unavailable"
    MODULE_NOT_FOUND = "module_not_found", "Module Not Found"
    MODULE_INACTIVE = "module_inactive", "Module Inactive"
    NOT_ACTIVATED = "not_activated", "Not Activated"
    ACTIVATION_DISABLED = "activation_disabled", "Activation Disabled"
    ACTIVATION_SUSPENDED = "activation_suspended", "Activation Suspended"
    SUBSCRIPTION_ACCOUNT_UNAVAILABLE = (
        "subscription_account_unavailable",
        "Subscription Account Unavailable",
    )
    VERIFICATION_REQUIRED = "verification_required", "Verification Required"
    ENTITLEMENT_REQUIRED = "entitlement_required", "Entitlement Required"


ORGANIZATION_MODULE_ENTITLEMENT_PREFIX = "organizations.modules."


DEFAULT_ORGANIZATION_MODULE_DEFINITIONS = (
    {
        "key": OrganizationModuleKey.CHURCH,
        "name": "Church & Congregational Life",
        "description": "Congregational operations, pastoral coordination, and church life tools.",
        "sort_order": 10,
    },
    {
        "key": OrganizationModuleKey.MISSIONS,
        "name": "Missions & Evangelism",
        "description": "Mission initiatives, evangelism programs, teams, and outreach coordination.",
        "sort_order": 20,
    },
    {
        "key": OrganizationModuleKey.EDUCATION,
        "name": "Education & Theological Training",
        "description": "Educational programs, theological training, courses, and learning operations.",
        "sort_order": 30,
    },
    {
        "key": OrganizationModuleKey.COUNSELING,
        "name": "Counseling, Pastoral Care & Recovery",
        "description": "Pastoral care, counseling, recovery, and support-service operations.",
        "sort_order": 40,
    },
    {
        "key": OrganizationModuleKey.WORSHIP,
        "name": "Worship, Music & Creative Arts",
        "description": "Worship teams, music, creative arts, and related ministry coordination.",
        "sort_order": 50,
    },
    {
        "key": OrganizationModuleKey.EVENTS,
        "name": "Events, Conferences & Retreats",
        "description": "Events, conferences, retreats, registrations, and operational coordination.",
        "sort_order": 60,
    },
    {
        "key": OrganizationModuleKey.CHILDREN_FAMILY,
        "name": "Children & Family Ministry",
        "description": "Children, family, parent-facing, and age-appropriate ministry operations.",
        "sort_order": 70,
    },
    {
        "key": OrganizationModuleKey.YOUTH_YOUNG_ADULTS,
        "name": "Youth & Young Adults",
        "description": "Youth and young-adult programs, groups, events, and ministry coordination.",
        "sort_order": 80,
    },
    {
        "key": OrganizationModuleKey.WOMEN,
        "name": "Women’s Ministry",
        "description": "Women’s ministry programs, groups, events, and care coordination.",
        "sort_order": 90,
    },
    {
        "key": OrganizationModuleKey.MEN,
        "name": "Men’s Ministry",
        "description": "Men’s ministry programs, groups, events, and care coordination.",
        "sort_order": 100,
    },
    {
        "key": OrganizationModuleKey.COMMUNITY_CARE,
        "name": "Community Care & Humanitarian Services",
        "description": "Community care, humanitarian assistance, relief, and local support programs.",
        "sort_order": 110,
    },
    {
        "key": OrganizationModuleKey.MEDIA_RESOURCES,
        "name": "Media, Publishing & Resource Library",
        "description": "Media, publishing, resource libraries, and organization-owned ministry resources.",
        "sort_order": 120,
    },
)


class OrganizationAuditSource(models.TextChoices):
    SERVICE = "service", "TownLIT Service"
    ADMIN = "admin", "TownLIT Admin"
    SYSTEM = "system", "System"
    GOVERNANCE = "governance", "Governance"


class OrganizationAuditAction(models.TextChoices):
    ORGANIZATION_CREATED = "organization_created", "Organization Created"
    ORGANIZATION_UPDATED = "organization_updated", "Organization Updated"
    FOLLOWED = "followed", "Organization Followed"
    UNFOLLOWED = "unfollowed", "Organization Unfollowed"
    MEMBERSHIP_REQUESTED = "membership_requested", "Membership Requested"
    MEMBERSHIP_INVITED = "membership_invited", "Membership Invited"
    MEMBERSHIP_ACCEPTED = "membership_accepted", "Membership Accepted"
    MEMBERSHIP_REJECTED = "membership_rejected", "Membership Rejected"
    MEMBERSHIP_WITHDRAWN = "membership_withdrawn", "Membership Withdrawn"
    MEMBERSHIP_CANCELED = "membership_canceled", "Membership Invitation Canceled"
    MEMBER_LEFT = "member_left", "Member Left"
    MEMBER_REMOVED = "member_removed", "Member Removed"
    ROLE_ASSIGNED = "role_assigned", "Role Assigned"
    ROLE_REVOKED = "role_revoked", "Role Revoked"
    MODULE_ENABLED = "module_enabled", "Organization Module Enabled"
    MODULE_DISABLED = "module_disabled", "Organization Module Disabled"
    MODULE_SUSPENDED = "module_suspended", "Organization Module Suspended"
    MODULE_RESTORED = "module_restored", "Organization Module Restored"
    MODULE_UPDATED = "module_updated", "Organization Module Updated"
    VERIFICATION_CASE_CREATED = "verification_case_created", "Verification Case Created"
    VERIFICATION_SUBMITTED = "verification_submitted", "Verification Submitted"
    VERIFICATION_NEEDS_INFORMATION = "verification_needs_information", "Verification Needs Information"
    VERIFICATION_APPROVED = "verification_approved", "Verification Approved"
    VERIFICATION_REJECTED = "verification_rejected", "Verification Rejected"
    VERIFICATION_WITHDRAWN = "verification_withdrawn", "Verification Withdrawn"
    VERIFICATION_REVOKED = "verification_revoked", "Verification Revoked"
    RELATIONSHIP_REQUESTED = "relationship_requested", "Relationship Requested"
    RELATIONSHIP_CONSENT_APPROVED = "relationship_consent_approved", "Relationship Consent Approved"
    RELATIONSHIP_CONSENT_REJECTED = "relationship_consent_rejected", "Relationship Consent Rejected"
    RELATIONSHIP_ACTIVATED = "relationship_activated", "Relationship Activated"
    RELATIONSHIP_ENDED = "relationship_ended", "Relationship Ended"
    GOVERNANCE_PROPOSAL_CREATED = "governance_proposal_created", "Governance Proposal Created"
    GOVERNANCE_PROPOSAL_OPENED = "governance_proposal_opened", "Governance Proposal Opened"
    GOVERNANCE_VOTE_CAST = "governance_vote_cast", "Governance Vote Cast"
    GOVERNANCE_DECIDED = "governance_decided", "Governance Decided"
    GOVERNANCE_EXECUTED = "governance_executed", "Governance Executed"
    GOVERNANCE_EXECUTION_FAILED = "governance_execution_failed", "Governance Execution Failed"
