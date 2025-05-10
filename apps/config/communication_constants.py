DRAFT = 'draft'
SENT = 'sent'
SCHEDULED = 'scheduled'
STATUS_CHOICES = [
    (DRAFT, 'Draft'),
    (SENT, 'Sent'),
    (SCHEDULED, 'Scheduled'),
]

ALL = 'all'
ACTIVE = 'active'
MEMBERS = 'members'
TARGET_GROUP_CHOICES = [
    (ALL, 'All Users'),
    (ACTIVE, 'Active Users'),
    (MEMBERS, 'Only Members'),
]