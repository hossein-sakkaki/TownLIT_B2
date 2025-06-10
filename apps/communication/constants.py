DRAFT = 'draft'
SENT = 'sent'
SCHEDULED = 'scheduled'
STATUS_CHOICES = [
    (DRAFT, 'Draft'),
    (SENT, 'Sent'),
    (SCHEDULED, 'Scheduled'),
]

BELIEVER = 'believer'
SEEKER = 'seeker'
PREFER_NOT = 'prefer_not_to_say'
ALL_ACTIVE = 'all_active'
SEEKER_AND_PREFER_NOT = 'seeker_and_prefer_not'
ADMINS = 'admins'
DELETED_MEMBERS = 'deleted_members'
DELETED_NON_MEMBERS = 'deleted_non_members'
SUSPENDED_USERS = 'suspended'
SANCTUARY_PARTICIPANTS = 'sanctuary_participants'
PRIVACY_ENABLED = 'privacy_enabled'
UNVERIFIED_IDENTITY = 'unverified_identity'
RE_ENGAGEMENT = 'reengagement'
ACCESS_REQUESTS = 'access_requests'

TARGET_GROUP_CHOICES = [
    (ALL_ACTIVE, 'All Active Users'),
    (BELIEVER, 'Label: Believers'),
    (SEEKER, 'Label: Seekers'),
    (PREFER_NOT, 'Label: Prefer Not to Say'),
    (SEEKER_AND_PREFER_NOT, 'Label: Seekers + Prefer Not to Say'),
    (ADMINS, 'TownLIT Admins'),
    (DELETED_MEMBERS, 'Deleted Member Accounts'),
    (DELETED_NON_MEMBERS, 'Deleted Non-Member Accounts'),
    (SUSPENDED_USERS, 'Suspended Accounts'),
    (SANCTUARY_PARTICIPANTS, 'Sanctuary-Eligible Members'),
    (PRIVACY_ENABLED, 'Members with Privacy Enabled'),
    (UNVERIFIED_IDENTITY, 'Members with Unverified Identity'),
    (RE_ENGAGEMENT, 'Previously Unsubscribed Users (Re-engagement Campaign)'),
    
    # 🔶 TEMPORARY: External invitees (not yet registered users)
    (ACCESS_REQUESTS, 'Pending Access Requests (pre-registration users)'),
]



# Email Template Layout Types --------------------------------------------
LAYOUT_BASE_EMAIL = 'base_email'
LAYOUT_BASE_SITE = 'base_site'
EMAIL_LAYOUT_CHOICES = [
    (LAYOUT_BASE_EMAIL, 'System Email (Security, Activation, etc.)_Base Email'),
    (LAYOUT_BASE_SITE, 'Campaign/Newsletter (Invitation, Updates)_Base Site'),
]