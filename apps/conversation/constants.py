# apps/conversation/constants.py

# DELETE POLICY Choices -----------------------------------------
SOFT_DELETE = 'soft_delete_for_user'
LEAVE_GROUP_SOFT_DELETE = 'leave_group_and_soft_delete'
DELETE_POLICY_CHOICES = [
    ('SOFT_DELETE', 'Soft Delete for User'),
    ('LEAVE_GROUP_SOFT_DELETE', 'Leave Group & Soft Delete'),
]

# MESSAGE POLICY Choices ----------------------------------------
DELETE_AFTER_VIEW = 'delete_after_view'
KEEP = 'keep'
MESSAGE_POLICY_CHOICES = [
    (DELETE_AFTER_VIEW, 'Delete After View'),
    (KEEP, 'Keep Message'),
]

# GROUP ROLE Choices --------------------------------------------
FOUNDER = 'founder'
ELDER = 'elder'
PARTICIPANT = 'participant'
GROUP_ROLE_CHOICES = [
    (FOUNDER, 'Founder'),
    (ELDER, 'Elder'),
    (PARTICIPANT, 'Participant'),
]

# SYSTEM MESSAGE EVENT Choices ----------------------------------
JOINED = 'joined'
LEFT = 'left'
REMOVED = 'removed'
FOUNDER_TRANSFERRED = 'founder_transferred'
PROMOTED_TO_ELDER = 'promoted_to_elder'
DEMOTED_TO_PARTICIPANT = 'demoted_to_participant'
GROUP_DELETED = 'group_deleted'
RESIGNED_FROM_ELDER = 'resigned_from_elder'
SYSTEM_MESSAGE_EVENT_CHOICES = [
    (JOINED, 'Joined'),
    (LEFT, 'Left'),
    (REMOVED, 'Removed'),
    (FOUNDER_TRANSFERRED, 'Founder Transferred'),
    (PROMOTED_TO_ELDER, 'Promoted to Elder'),
    (DEMOTED_TO_PARTICIPANT, 'Demoted to Participant'),
    (GROUP_DELETED, 'Group Deleted'),
    (RESIGNED_FROM_ELDER, 'Resigned from Elder Role'),
]


# MESSAGE PIN DURATION Choices --------------------------------
PIN_NONE = "none"
PIN_1_HOUR = "1_hour"
PIN_24_HOURS = "24_hours"
PIN_1_WEEK = "1_week"
PIN_1_MONTH = "1_month"
PIN_3_MONTHS = "3_months"

MESSAGE_PIN_DURATION_CHOICES = [
    (PIN_NONE, "No Expiry"),
    (PIN_1_HOUR, "1 Hour"),
    (PIN_24_HOURS, "24 Hours"),
    (PIN_1_WEEK, "1 Week"),
    (PIN_1_MONTH, "1 Month"),
    (PIN_3_MONTHS, "3 Months"),
]


# MESSAGE REACTION TYPE Choices ------------------------------
MSG_LIKE = "like"
MSG_DISLIKE = "dislike"
MSG_GRATITUDE = "gratitude"
MSG_HEART = "heart"
MSG_ENCOURAGEMENT = "encouragement"

MESSAGE_REACTION_TYPE_CHOICES = [
    (MSG_LIKE, "Like"),
    (MSG_DISLIKE, "Dislike"),
    (MSG_GRATITUDE, "Gratitude"),
    (MSG_HEART, "Heart"),
    (MSG_ENCOURAGEMENT, "Encouragement"),
]