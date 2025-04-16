

SOFT_DELETE = 'soft_delete_for_user'
LEAVE_GROUP_SOFT_DELETE = 'leave_group_and_soft_delete'
DELETE_POLICY_CHOICES = [
    ('SOFT_DELETE', 'Soft Delete for User'),
    ('LEAVE_GROUP_SOFT_DELETE', 'Leave Group & Soft Delete'),
]




# MESSAGE POLICY Choices
DELETE_AFTER_VIEW = 'delete_after_view'
KEEP = 'keep'
MESSAGE_POLICY_CHOICES = [
    (DELETE_AFTER_VIEW, 'Delete After View'),
    (KEEP, 'Keep Message'),
]


FOUNDER = 'founder'
ELDER = 'elder'
PARTICIPANT = 'participant'
GROUP_ROLE_CHOICES = [
    (FOUNDER, 'Founder'),
    (ELDER, 'Elder'),
    (PARTICIPANT, 'Participant'),
]


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
