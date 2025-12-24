# apps/sanctuary/constants/reasons.py
# ============================================================
# SANCTUARY REASONS
# Why a Sanctuary request is submitted
# ============================================================

# ------------------------
# CONTENT (ALL POST TYPES)
# ------------------------

HATE_SPEECH = 'hate_speech'
INCITEMENT_TO_HATRED = 'incitement_to_hatred'
VIOLENT_CONTENT = 'violent_content'

SEXUALLY_INAPPROPRIATE_CONTENT = 'sexually_inappropriate_content'
SPIRITUAL_ABUSE = 'spiritual_abuse'

FALSE_TEACHING_SALVATION = 'false_teaching_salvation'
FALSE_GOSPEL = 'false_gospel'
DISTORTION_OF_SCRIPTURE = 'distortion_of_scripture'
DOCTRINAL_DECEPTION = 'doctrinal_deception'
CULT_PROMOTION = 'cult_promotion'

MISREPRESENTATION_OF_CHRISTIAN_FAITH = 'misrepresentation_of_christian_faith'
DELIBERATE_PROVOCATION = 'deliberate_provocation'

FALSE_INFORMATION = 'false_information'
INTELLECTUAL_PROPERTY_VIOLATION = 'intellectual_property_violation'
SPAM = 'spam'
TERRORIST_CONTENT = 'terrorist_content'

OTHER_CONTENT = 'other_content'

CONTENT_REPORT_CHOICES = [
    (HATE_SPEECH, 'Hate Speech'),
    (INCITEMENT_TO_HATRED, 'Incitement to Hatred'),
    (VIOLENT_CONTENT, 'Violent Content'),
    (SEXUALLY_INAPPROPRIATE_CONTENT, 'Sexually Inappropriate Content'),
    (SPIRITUAL_ABUSE, 'Spiritual Abuse'),
    (FALSE_TEACHING_SALVATION, 'False Teaching on Salvation'),
    (FALSE_GOSPEL, 'False Gospel'),
    (DISTORTION_OF_SCRIPTURE, 'Distortion of Scripture'),
    (DOCTRINAL_DECEPTION, 'Doctrinal Deception'),
    (CULT_PROMOTION, 'Cult Promotion'),
    (MISREPRESENTATION_OF_CHRISTIAN_FAITH, 'Misrepresentation of Christian Faith'),
    (DELIBERATE_PROVOCATION, 'Deliberate Provocation'),
    (FALSE_INFORMATION, 'False Information'),
    (INTELLECTUAL_PROPERTY_VIOLATION, 'Intellectual Property Violation'),
    (SPAM, 'Spam'),
    (TERRORIST_CONTENT, 'Terrorist Content'),
    (OTHER_CONTENT, 'Other'),
]

# ------------------------
# PERSONAL ACCOUNT
# ------------------------

FRAUD = 'fraud'
FAKE_IDENTITY = 'fake_identity'
IMPERSONATION_OF_CHRISTIAN_LEADER = 'impersonation_of_christian_leader'

HARASSMENT = 'harassment'
TARGETED_HARASSMENT = 'targeted_harassment'
THREATENING_LANGUAGE = 'threatening_language'

PRIVACY_VIOLATION = 'privacy_violation'
ILLEGAL_ACTIVITIES = 'illegal_activities'

VIOLATION_BIBLICAL_MORALS = 'violation_biblical_morals'
HERESY_ON_NATURE_OF_GOD = 'heresy_on_nature_of_god'
BLASPHEMY = 'blasphemy'

SPIRITUAL_MANIPULATION = 'spiritual_manipulation'
ABUSE_OF_AUTHORITY = 'abuse_of_authority'
SECTARIAN_DIVISION = 'sectarian_division'

REPEATED_FALSE_REPORTING = 'repeated_false_reporting'
MISUSE_OF_TOWNLIT = 'misuse_of_townlit'
VIOLATION_TOWNLIT_POLICIES = 'violation_townlit_policies'

OTHER_ACCOUNT = 'other_account'

ACCOUNT_REPORT_CHOICES = [
    (FRAUD, 'Fraud or Scam'),
    (FAKE_IDENTITY, 'Fake Identity'),
    (IMPERSONATION_OF_CHRISTIAN_LEADER, 'Impersonation of Christian Leader'),
    (HARASSMENT, 'Harassment or Bullying'),
    (TARGETED_HARASSMENT, 'Targeted Harassment'),
    (THREATENING_LANGUAGE, 'Threatening Language'),
    (PRIVACY_VIOLATION, 'Privacy Violation'),
    (ILLEGAL_ACTIVITIES, 'Illegal Activities'),
    (VIOLATION_BIBLICAL_MORALS, 'Violation of Biblical Moral Principles'),
    (HERESY_ON_NATURE_OF_GOD, 'Heresy on the Nature of God'),
    (BLASPHEMY, 'Blasphemy'),
    (SPIRITUAL_MANIPULATION, 'Spiritual Manipulation'),
    (ABUSE_OF_AUTHORITY, 'Abuse of Authority'),
    (SECTARIAN_DIVISION, 'Sectarian Division'),
    (REPEATED_FALSE_REPORTING, 'Repeated False Reporting'),
    (MISUSE_OF_TOWNLIT, 'Misuse of TownLIT'),
    (VIOLATION_TOWNLIT_POLICIES, 'Violation of TownLIT Policies'),
    (OTHER_ACCOUNT, 'Other'),
]

# ------------------------
# ORGANIZATION
# ------------------------

MISMANAGEMENT_OF_FUNDS = 'mismanagement_of_funds'
FINANCIAL_OPACITY = 'financial_opacity'
MISUSE_OF_DONATIONS = 'misuse_of_donations'

DOCTRINAL_OPACITY = 'doctrinal_opacity'
ABUSIVE_DISCIPLESHIP = 'abusive_discipleship'
SPIRITUAL_COERCION = 'spiritual_coercion'

LEADERSHIP_IMMORALITY = 'leadership_immorality'
LACK_OF_ACCOUNTABILITY = 'lack_of_accountability'

ORGANIZATION_REPORT_CHOICES = [
    (FRAUD, 'Fraud or Scam'),
    (PRIVACY_VIOLATION, 'Privacy Violation'),
    (HARASSMENT, 'Harassment or Bullying'),
    (FAKE_IDENTITY, 'Fake Identity'),
    (MISMANAGEMENT_OF_FUNDS, 'Mismanagement of Funds'),
    (FINANCIAL_OPACITY, 'Financial Opacity'),
    (MISUSE_OF_DONATIONS, 'Misuse of Donations'),
    (DOCTRINAL_OPACITY, 'Doctrinal Opacity'),
    (ABUSIVE_DISCIPLESHIP, 'Abusive Discipleship'),
    (SPIRITUAL_COERCION, 'Spiritual Coercion'),
    (LEADERSHIP_IMMORALITY, 'Leadership Immorality'),
    (LACK_OF_ACCOUNTABILITY, 'Lack of Accountability'),
]

# ------------------------
# MESSENGER GROUP
# ------------------------

GROUP_HARASSMENT = 'group_harassment'
COORDINATED_ATTACK = 'coordinated_attack'
EXCLUSIONARY_BEHAVIOR = 'exclusionary_behavior'
ABUSIVE_GROUP_LEADERSHIP = 'abusive_group_leadership'
MANIPULATIVE_GROUP_TEACHING = 'manipulative_group_teaching'
UNSAFE_ENVIRONMENT = 'unsafe_environment'

MESSENGER_GROUP_REPORT_CHOICES = [
    (GROUP_HARASSMENT, 'Group Harassment'),
    (COORDINATED_ATTACK, 'Coordinated Attack'),
    (EXCLUSIONARY_BEHAVIOR, 'Exclusionary Behavior'),
    (ABUSIVE_GROUP_LEADERSHIP, 'Abusive Group Leadership'),
    (MANIPULATIVE_GROUP_TEACHING, 'Manipulative Group Teaching'),
    (UNSAFE_ENVIRONMENT, 'Unsafe Environment'),
]


# Map request_type → allowed reasons --------------------------------------------------------
REASON_MAP = {
    "content": dict(CONTENT_REPORT_CHOICES),
    "account": dict(ACCOUNT_REPORT_CHOICES),
    "organization": dict(ORGANIZATION_REPORT_CHOICES),
    "messenger_group": dict(MESSENGER_GROUP_REPORT_CHOICES),
}