from django.utils.translation import gettext_lazy as _


ENGLISH = 'en'
PERSIAN = 'fa'
TURKISH = 'tr'
SPANISH = 'es'
CHINESE = 'zh'
ARABIC = 'ar'
KOREAN = 'ko'
FRENCH = 'fr'
GERMAN = 'de'
ITALIAN = 'it'
PORTUGUESE = 'pt'
RUSSIAN = 'ru'
JAPANESE = 'ja'
HINDI = 'hi'
BENGALI = 'bn'
URDU = 'ur'
INDONESIAN = 'id'
TAMIL = 'ta'
MALAY = 'ms'
VIETNAMESE = 'vi'
THAI = 'th'

LANGUAGE_CHOICES = [
    (ENGLISH, _('English')),
    (PERSIAN, _('Persian')),
    (TURKISH, _('Turkish')),
    (SPANISH, _('Spanish')),
    (CHINESE, _('Chinese')),
    (ARABIC, _('Arabic')),
    (KOREAN, _('Korean')),
    (FRENCH, _('French')),
    (GERMAN, _('German')),
    (ITALIAN, _('Italian')),
    (PORTUGUESE, _('Portuguese')),
    (RUSSIAN, _('Russian')),
    (JAPANESE, _('Japanese')),
    (HINDI, _('Hindi')),
    (BENGALI, _('Bengali')),
    (URDU, _('Urdu')),
    (INDONESIAN, _('Indonesian')),
    (TAMIL, _('Tamil')),
    (MALAY, _('Malay')),
    (VIETNAMESE, _('Vietnamese')),
    (THAI, _('Thai')),
]


# POLICY OF TOWNNLIT Choices ------------------------------------------------------------
PRIVACY_POLICY = 'privacy_policy'
TERMS_OF_SERVICE = 'terms_of_service'
COMMUNITY_GUIDELINES = 'community_guidelines'
DATA_USAGE_POLICY = 'data_usage_policy'
CONTENT_MODERATION_POLICY = 'content_moderation_policy'
COPYRIGHT_POLICY = 'copyright_policy'
DISPUTE_RESOLUTION = 'dispute_resolution'
VISION_AND_MISSION = 'vision_and_mission'
TOWNLIT_HISTORY = 'townlit_history'
TOWNLIT_BELIEFS = 'townlit_beliefs'
TERMS_AND_CONDITIONS = 'terms_and_conditions'   
COOKIE_POLICY = 'cookie_policy'
TERMS_AND_POLICIES_CHOICES = [
    (PRIVACY_POLICY, 'Privacy Policy'),
    (TERMS_OF_SERVICE, 'Terms of Service'),
    (COMMUNITY_GUIDELINES, 'Community Guidelines'),
    (DATA_USAGE_POLICY, 'Data Usage Policy'),
    (CONTENT_MODERATION_POLICY, 'Content Moderation Policy'),
    (COPYRIGHT_POLICY, 'Copyright Policy'),
    (DISPUTE_RESOLUTION, 'Dispute Resolution and Arbitration'),
    (VISION_AND_MISSION, 'Vision and Mission'),
    (TOWNLIT_HISTORY, 'TownLIT History'),
    (TOWNLIT_BELIEFS, 'TownLIT Beliefs'),
    (TERMS_AND_CONDITIONS, 'Terms and Conditions'),
    (COOKIE_POLICY, 'Cookie Policy'),
]


# DISPLAY LOCATIONS for Terms and Policies --------------------------------------------
DISPLAY_IN_FOOTER = 'footer'
DISPLAY_IN_OFFICIAL = 'official'
DISPLAY_IN_BOTH = 'both'
POLICY_DISPLAY_LOCATION_CHOICES = [
    (DISPLAY_IN_FOOTER, 'Footer'),
    (DISPLAY_IN_OFFICIAL, 'Official Info Page'),
    (DISPLAY_IN_BOTH, 'Both'),
]


# DISPLAY LOCATIONS for Terms and Policies (Left or Right) -----------------------------
FOOTER_LEFT = 'left'
FOOTER_RIGHT = 'right'
FOOTER_COLUMN_CHOICES = [
    (FOOTER_LEFT, 'Left Column'),
    (FOOTER_RIGHT, 'Right Column'),
]


# LOG ACTION Choices ---------------------------------------------------------------------
VIEW = 'view'
EDIT = 'edit'
DELETE = 'delete'
LOG_ACTION_CHOICES = [
    (VIEW, 'View'),
    (EDIT, 'Edit'),
    (DELETE, 'Delete'),
]

# USER FEEDBACK STATUS Choices -----------------------------------------------------------
NEW = 'new'
REVIEWED = 'reviewed'
RESOLVED = 'resolved'
USER_FEEDBACK_STATUS_CHOICES = [
    (NEW, 'New'),
    (REVIEWED, 'Reviewed'),
    (RESOLVED, 'Resolved'),
]

