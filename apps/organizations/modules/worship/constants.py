# apps/organizations/modules/worship/constants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.db import models


class WorshipRightsPartyRelationship(models.TextChoices):
    SELF = "self", "Organization / Self"
    LICENSOR = "licensor", "Licensor"
    REPRESENTATIVE = "representative", "Representative"
    PARTNER = "partner", "Partner"
    OTHER = "other", "Other"


class OrganizationMusicLicenseStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"


class OrganizationMusicContributionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    REVOKED = "revoked", "Revoked"


class WorshipPermissionKey:
    VIEW_MUSIC = "organizations.modules.worship.music.view"
    MANAGE_RIGHTS = "organizations.modules.worship.rights.manage"
    MANAGE_LICENSES = "organizations.modules.worship.licenses.manage"
    MANAGE_CONTRIBUTIONS = "organizations.modules.worship.contributions.manage"
    PUBLISH_CONTRIBUTIONS = "organizations.modules.worship.contributions.publish"


WORSHIP_PERMISSION_DEFINITIONS = (
    (WorshipPermissionKey.VIEW_MUSIC, "View Worship Music", "worship", "View Organization music licensing and contribution records."),
    (WorshipPermissionKey.MANAGE_RIGHTS, "Manage Worship Rights Parties", "worship", "Manage legal parties used by Organization music licensing."),
    (WorshipPermissionKey.MANAGE_LICENSES, "Manage Worship Music Licenses", "worship", "Create, activate, and revoke Organization music licenses."),
    (WorshipPermissionKey.MANAGE_CONTRIBUTIONS, "Manage Worship Music Contributions", "worship", "Create and prepare Organization music contributions for the TownLIT Audio Catalog."),
    (WorshipPermissionKey.PUBLISH_CONTRIBUTIONS, "Publish Worship Music Contributions", "worship", "Publish and revoke Organization-contributed music in the TownLIT Audio Catalog."),
)


class WorshipRoleKey:
    ADMINISTRATOR = "worship_administrator"
    RIGHTS_MANAGER = "worship_rights_manager"
    MUSIC_MANAGER = "worship_music_manager"
    CONTRIBUTOR = "worship_contributor"


WORSHIP_ROLE_DEFINITIONS = (
    {
        "key": WorshipRoleKey.ADMINISTRATOR,
        "name": "Worship Administrator",
        "description": "Full administration of Worship music rights, licenses, and contributions.",
        "priority": 650,
        "permissions": tuple(item[0] for item in WORSHIP_PERMISSION_DEFINITIONS),
    },
    {
        "key": WorshipRoleKey.RIGHTS_MANAGER,
        "name": "Worship Rights Manager",
        "description": "Manages legal parties and Organization music licenses.",
        "priority": 620,
        "permissions": (
            WorshipPermissionKey.VIEW_MUSIC,
            WorshipPermissionKey.MANAGE_RIGHTS,
            WorshipPermissionKey.MANAGE_LICENSES,
        ),
    },
    {
        "key": WorshipRoleKey.MUSIC_MANAGER,
        "name": "Worship Music Manager",
        "description": "Prepares and publishes Organization music contributions.",
        "priority": 560,
        "permissions": (
            WorshipPermissionKey.VIEW_MUSIC,
            WorshipPermissionKey.MANAGE_CONTRIBUTIONS,
            WorshipPermissionKey.PUBLISH_CONTRIBUTIONS,
        ),
    },
    {
        "key": WorshipRoleKey.CONTRIBUTOR,
        "name": "Worship Contributor",
        "description": "Prepares Organization music contribution drafts without publication rights.",
        "priority": 500,
        "permissions": (
            WorshipPermissionKey.VIEW_MUSIC,
            WorshipPermissionKey.MANAGE_CONTRIBUTIONS,
        ),
    },
)


class WorshipAuditEvent(models.TextChoices):
    WORKSPACE_INITIALIZED = "workspace_initialized", "Workspace Initialized"
    RIGHTS_PARTY_LINKED = "rights_party_linked", "Rights Party Linked"
    RIGHTS_PARTY_DEACTIVATED = "rights_party_deactivated", "Rights Party Deactivated"
    LICENSE_CREATED = "license_created", "License Created"
    LICENSE_EVIDENCE_ADDED = "license_evidence_added", "License Evidence Added"
    LICENSE_ACTIVATED = "license_activated", "License Activated"
    LICENSE_REVOKED = "license_revoked", "License Revoked"
    CONTRIBUTION_CREATED = "contribution_created", "Contribution Created"
    CONTRIBUTION_PUBLISHED = "contribution_published", "Contribution Published"
    CONTRIBUTION_REVOKED = "contribution_revoked", "Contribution Revoked"
