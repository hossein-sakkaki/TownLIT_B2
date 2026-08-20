# apps/communication/constants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.db import models


# Campaign status -------------------------------------------------------------

class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    REVIEW = "review", "Needs Review"
    READY = "ready", "Ready to Send"
    SCHEDULED = "scheduled", "Scheduled"
    QUEUED = "queued", "Queued"
    SENDING = "sending", "Sending"
    PAUSED = "paused", "Paused"
    SENT = "sent", "Sent"
    CANCELED = "canceled", "Canceled"
    FAILED = "failed", "Failed"


DRAFT = CampaignStatus.DRAFT
SENT = CampaignStatus.SENT
SCHEDULED = CampaignStatus.SCHEDULED
STATUS_CHOICES = CampaignStatus.choices


# Campaign type ---------------------------------------------------------------

class CampaignType(models.TextChoices):
    NEWSLETTER = "newsletter", "Newsletter"
    ANNOUNCEMENT = "announcement", "Announcement"
    COMMUNITY = "community", "Community Update"
    EVENT = "event", "Event"
    DEVOTIONAL = "devotional", "Devotional / Encouragement"
    REENGAGEMENT = "reengagement", "Re-engagement"
    OPERATIONAL = "operational", "Operational"
    OTHER = "other", "Other"


# Legacy audience presets -----------------------------------------------------

BELIEVER = "believer"
SEEKER = "seeker"
PREFER_NOT = "prefer_not_to_say"
ALL_ACTIVE = "all_active"
SEEKER_AND_PREFER_NOT = "seeker_and_prefer_not"
ADMINS = "admins"
DELETED_MEMBERS = "deleted_members"
DELETED_NON_MEMBERS = "deleted_non_members"
SUSPENDED_USERS = "suspended"
SANCTUARY_PARTICIPANTS = "sanctuary_participants"
PRIVACY_ENABLED = "privacy_enabled"
UNVERIFIED_IDENTITY = "unverified_identity"
TOWNLIT_VERIFIED = "townlit_verified"
TOWNLIT_NOT_VERIFIED = "townlit_not_verified"
RE_ENGAGEMENT = "reengagement"

# Legacy compatibility only.
ACCESS_REQUESTS = "access_requests"
UNUSED_INVITE_ACCESS = "unused_invite_access_requests"


TARGET_GROUP_CHOICES = [
    (ALL_ACTIVE, "All Active Users"),
    (BELIEVER, "Label: Believers"),
    (SEEKER, "Label: Seekers"),
    (PREFER_NOT, "Label: Prefer Not to Say"),
    (
        SEEKER_AND_PREFER_NOT,
        "Label: Seekers + Prefer Not to Say",
    ),
    (ADMINS, "TownLIT Admins"),
    (DELETED_MEMBERS, "Deleted Member Accounts"),
    (
        DELETED_NON_MEMBERS,
        "Deleted Non-Member Accounts",
    ),
    (SUSPENDED_USERS, "Suspended Accounts"),
    (
        SANCTUARY_PARTICIPANTS,
        "Sanctuary-Eligible Members",
    ),
    (
        PRIVACY_ENABLED,
        "Members with Privacy Enabled",
    ),
    (
        UNVERIFIED_IDENTITY,
        "Members with Unverified Identity",
    ),
    (
        TOWNLIT_VERIFIED,
        "TownLIT Verified Members",
    ),
    (
        TOWNLIT_NOT_VERIFIED,
        "TownLIT Not Yet Verified Members",
    ),
    (
        RE_ENGAGEMENT,
        "Previously Unsubscribed Users",
    ),

    # Legacy compatibility only.
    (
        ACCESS_REQUESTS,
        "Legacy: Pending Access Requests",
    ),
    (
        UNUSED_INVITE_ACCESS,
        "Legacy: Access Requests with Unused Invite Codes",
    ),
]


# Email layouts ---------------------------------------------------------------

LAYOUT_BASE_EMAIL = "base_email"
LAYOUT_BASE_SITE = "base_site"

EMAIL_LAYOUT_CHOICES = [
    (
        LAYOUT_BASE_EMAIL,
        "System Email",
    ),
    (
        LAYOUT_BASE_SITE,
        "Campaign / Newsletter",
    ),
]


# Template --------------------------------------------------------------------

class EmailTemplateCategory(models.TextChoices):
    GENERAL = "general", "General"
    NEWSLETTER = "newsletter", "Newsletter"
    ANNOUNCEMENT = "announcement", "Announcement"
    COMMUNITY = "community", "Community"
    EVENT = "event", "Event"
    DEVOTIONAL = "devotional", "Devotional"
    WELCOME = "welcome", "Welcome"
    REENGAGEMENT = "reengagement", "Re-engagement"
    SYSTEM = "system", "System"
    OTHER = "other", "Other"


class EmailEditorMode(models.TextChoices):
    RICH_TEXT = "rich_text", "Rich Text"
    BLOCKS = "blocks", "Block Builder"
    HTML = "html", "Custom HTML"


class EmailBlockType(models.TextChoices):
    HERO = "hero", "Hero"
    TEXT = "text", "Text"
    IMAGE = "image", "Image"
    BUTTON = "button", "Button"
    QUOTE = "quote", "Quote"
    CALLOUT = "callout", "Callout"
    DIVIDER = "divider", "Divider"
    SPACER = "spacer", "Spacer"
    TWO_COLUMN = "two_column", "Two Columns"
    SOCIAL_LINKS = "social_links", "Social Links"
    CUSTOM_HTML = "custom_html", "Custom HTML"


# Audience --------------------------------------------------------------------

class AudienceKind(models.TextChoices):
    DYNAMIC = "dynamic", "Dynamic Audience"
    MANUAL = "manual", "Manual Audience"
    HYBRID = "hybrid", "Rules + Manual Selection"
    PRESET = "preset", "TownLIT Preset"


class AudienceMatchType(models.TextChoices):
    ALL = "all", "Match All Rules"
    ANY = "any", "Match Any Rule"


class AudienceRuleField(models.TextChoices):
    ACTIVE = "is_active", "Account Active"
    MEMBER = "is_member", "Member"
    ADMIN = "is_admin", "Administrator"
    SUSPENDED = "is_suspended", "Suspended"
    LABEL = "label", "Account Label"
    COUNTRY = "country", "Country"
    CITY = "city", "City"
    PRIMARY_LANGUAGE = "primary_language", "Primary Language"
    SECONDARY_LANGUAGE = "secondary_language", "Secondary Language"
    REGISTER_DATE = "register_date", "Registration Date"


class AudienceRuleOperator(models.TextChoices):
    EQUALS = "equals", "Equals"
    NOT_EQUALS = "not_equals", "Does Not Equal"
    IN = "in", "Is One Of"
    NOT_IN = "not_in", "Is Not One Of"
    TRUE = "true", "Is True"
    FALSE = "false", "Is False"
    CONTAINS = "contains", "Contains"
    BEFORE = "before", "Before"
    AFTER = "after", "After"


# Delivery --------------------------------------------------------------------

class EmailDeliveryStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    BOUNCED = "bounced", "Bounced"
    COMPLAINED = "complained", "Complaint"
    SUPPRESSED = "suppressed", "Suppressed"
    FAILED = "failed", "Failed"


class EmailDeliveryProvider(models.TextChoices):
    AWS_SES = "aws_ses", "AWS SES"


class EmailEventType(models.TextChoices):
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    OPENED = "opened", "Opened"
    CLICKED = "clicked", "Clicked"
    BOUNCED = "bounced", "Bounced"
    COMPLAINED = "complained", "Complaint"
    UNSUBSCRIBED = "unsubscribed", "Unsubscribed"
    FAILED = "failed", "Failed"


# Subscription ---------------------------------------------------------------

class EmailSubscriptionStatus(models.TextChoices):
    SUBSCRIBED = "subscribed", "Subscribed"
    UNSUBSCRIBED = "unsubscribed", "Unsubscribed"


class EmailSubscriptionSource(models.TextChoices):
    ACCOUNT = "account", "Account Settings"
    EMAIL_LINK = "email_link", "Email Link"
    ADMIN = "admin", "Administrator"
    IMPORT = "import", "Imported"
    SYSTEM = "system", "System"


class EmailUnsubscribeScope(models.TextChoices):
    MARKETING = "marketing", "Marketing Emails"
    ALL_OPTIONAL = "all_optional", "All Optional Emails"