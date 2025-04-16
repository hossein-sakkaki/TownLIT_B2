# SANCTUARY POST Choices ---------------------------------------------------------------------------
HATE_SPEECH = 'hate_speech'
VIOLENT_CONTENT = 'violent_content'
FALSE_TEACHING_SALVATION = 'false_teaching_salvation'
FALSE_GOSPEL = 'false_gospel'
DISTORTION_OF_SCRIPTURE = 'distortion_of_scripture'
INTELLECTUAL_PROPERTY_VIOLATION = 'intellectual_property_violation'
SEXUALLY_INAPPROPRIATE_CONTENT = 'sexually_inappropriate_content'
TERRORIST_CONTENT = 'terrorist_content'
FALSE_INFORMATION = 'false_information'
SPAM = 'spam'
OTHER = 'other'
POST_REPORT_CHOICES = [
    (HATE_SPEECH, 'Hate Speech'),
    (VIOLENT_CONTENT, 'Violent Content'),
    (FALSE_TEACHING_SALVATION, 'False Teaching on Salvation'),
    (FALSE_GOSPEL, 'Promoting a False Gospel'),
    (DISTORTION_OF_SCRIPTURE, 'Distortion of Scripture'),
    (INTELLECTUAL_PROPERTY_VIOLATION, 'Intellectual Property Violation'),
    (SEXUALLY_INAPPROPRIATE_CONTENT, 'Sexually Inappropriate Content'),
    (TERRORIST_CONTENT, 'Terrorist Content'),
    (FALSE_INFORMATION, 'False Information'),
    (SPAM, 'Spam'),
    (OTHER, 'Other'),
]


# SANCTUARY ACCOUNT Choices ------------------------------------------------------------------------
FRAUD = 'fraud'
PRIVACY_VIOLATION = 'privacy_violation'
MISUSE_OF_TOWNLIT = 'misuse_of_townlit'
ILLEGAL_ACTIVITIES = 'illegal_activities'
HARASSMENT = 'harassment'
VIOLATION_BIBLICAL_MORALS = 'violation_biblical_morals'
HERESY_ON_NATURE_OF_GOD = 'heresy_on_nature_of_god'
FALSE_INFORMATION_ACCOUNT = 'false_information_account'
BLASPHEMY = 'blasphemy'
VIOLATION_TOWNLIT_POLICIES = 'violation_townlit_policies'
FAKE_IDENTITY = 'fake_identity'
OTHER = 'other'
ACCOUNT_REPORT_CHOICES = [
    (FRAUD, 'Fraud or Scam'),
    (PRIVACY_VIOLATION, 'Privacy Violation'),
    (MISUSE_OF_TOWNLIT, 'Misuse of TownLIT'),
    (ILLEGAL_ACTIVITIES, 'Illegal Activities'),
    (HARASSMENT, 'Harassment or Bullying'),
    (VIOLATION_BIBLICAL_MORALS, 'Violation of Biblical Moral Principles'),
    (HERESY_ON_NATURE_OF_GOD, 'Heresy on the Nature of God'),
    (FALSE_INFORMATION_ACCOUNT, 'False Information'),
    (BLASPHEMY, 'Blasphemy'),
    (VIOLATION_TOWNLIT_POLICIES, 'Violation of TownLIT Policies'),
    (FAKE_IDENTITY, 'Fake Identity'),
    (OTHER, 'Other'),
]


# SANCTUARY ORGANIZATION Choices -------------------------------------------------------------------------
FRAUD_ORGANIZATION = 'fraud'
PRIVACY_VIOLATION_ORGANIZATION = 'privacy_violation'
MISUSE_OF_TOWNLIT_ORGANIZATION = 'misuse_of_townlit'
ILLEGAL_ACTIVITIES_ORGANIZATION = 'illegal_activities'
HARASSMENT_ORGANIZATION = 'harassment'
VIOLATION_BIBLICAL_MORALS_ORGANIZATION = 'violation_biblical_morals'
HERESY_ON_NATURE_OF_GOD_ORGANIZATION = 'heresy_on_nature_of_god'
FALSE_INFORMATION_ORGANIZATION = 'false_information_organization'
BLASPHEMY_ORGANIZATION = 'blasphemy'
VIOLATION_TOWNLIT_POLICIES_ORGANIZATION = 'violation_townlit_policies'
FAKE_IDENTITY_ORGANIZATION = 'fake_identity'
MISMANAGEMENT_OF_FUNDS = 'mismanagement_of_funds'
VIOLATION_ORGANIZATIONAL_GUIDELINES = 'violation_organizational_guidelines'
OTHER_ORGANIZATION = 'other'

ORGANIZATION_REPORT_CHOICES = [
    (FRAUD_ORGANIZATION, 'Fraud or Scam'),
    (PRIVACY_VIOLATION_ORGANIZATION, 'Privacy Violation'),
    (MISUSE_OF_TOWNLIT_ORGANIZATION, 'Misuse of TownLIT'),
    (ILLEGAL_ACTIVITIES_ORGANIZATION, 'Illegal Activities'),
    (HARASSMENT_ORGANIZATION, 'Harassment or Bullying'),
    (VIOLATION_BIBLICAL_MORALS_ORGANIZATION, 'Violation of Biblical Moral Principles'),
    (HERESY_ON_NATURE_OF_GOD_ORGANIZATION, 'Heresy on the Nature of God'),
    (FALSE_INFORMATION_ORGANIZATION, 'False Information'),
    (BLASPHEMY_ORGANIZATION, 'Blasphemy'),
    (VIOLATION_TOWNLIT_POLICIES_ORGANIZATION, 'Violation of TownLIT Policies'),
    (FAKE_IDENTITY_ORGANIZATION, 'Fake Identity'),
    (MISMANAGEMENT_OF_FUNDS, 'Mismanagement of Funds'),
    (VIOLATION_ORGANIZATIONAL_GUIDELINES, 'Violation of Organizational Guidelines'),
    (OTHER_ORGANIZATION, 'Other'),
]

# SENSITIVE CASES FOR ADMIN REVIEW -----------------------------------------------------------------------
POST_ADMIN_REVIEW_CATEGORIES = [
    'sexually_inappropriate_content', 
    'terrorist_content', 
    'intellectual_property_violation', 
    'violent_content', 
    'other'
]

ACCOUNT_ADMIN_REVIEW_CATEGORIES = [
    'fraud', 
    'privacy_violation', 
    'harassment', 
    'fake_identity', 
    'other'
]

ORGANIZATION_ADMIN_REVIEW_CATEGORIES = [
    'fraud', 
    'privacy_violation', 
    'harassment', 
    'fake_identity', 
    'mismanagement_of_funds', 
    'other'
]

# Combine sensitive categories into one dictionary
SENSITIVE_CATEGORIES = {
    'post_request': POST_ADMIN_REVIEW_CATEGORIES,
    'account_request': ACCOUNT_ADMIN_REVIEW_CATEGORIES,
    'organization_request': ORGANIZATION_ADMIN_REVIEW_CATEGORIES
}


# REQUEST TYPE Choices ---------------------------------------------------------------------------
POST_REQUEST = 'post_request'
ACCOUNT_REQUEST = 'account_request'
ORGANIZATION_REQUEST = 'organization_request'
REQUEST_TYPE_CHOICES = [
    (POST_REQUEST, 'Post Request'),
    (ACCOUNT_REQUEST, 'Account Request'),
    (ORGANIZATION_REQUEST, 'Organization Request'),
]


# REQUEST STATUS Choices --------------------------------------------------------------------------
PENDING = 'pending'
UNDER_REVIEW = 'under_review'
RESOLVED = 'resolved'
REJECTED = 'rejected'
REQUEST_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (UNDER_REVIEW, 'Under Review'),
    (RESOLVED, 'Resolved'),
    (REJECTED, 'Rejected'),
]


# REVIEW STATUS Choices --------------------------------------------------------------------------
NO_OPINION = 'no_opinion'
VIOLATION_CONFIRMED = 'violation_confirmed'
VIOLATION_REJECTED = 'violation_rejected'
REVIEW_STATUS_CHOICES = [
    (NO_OPINION, 'No Opinion'),
    (VIOLATION_CONFIRMED, 'Violation Confirmed'),
    (VIOLATION_REJECTED, 'Violation Rejected'),
]


# OUTCOME Choices --------------------------------------------------------------------------------
OUTCOME_CONFIRMED = 'outcome_confirmed'
OUTCOME_REJECTED = 'outcome_rejected'
OUTCOME_PENDING = 'outcome_pending'
OUTCOME_CHOICES = [
    (OUTCOME_CONFIRMED, 'Confirmed'),
    (OUTCOME_REJECTED, 'Rejected'),
    (OUTCOME_PENDING, 'Pending'),
]