# apps/sanctuary/constants/targets.py
# ============================================================
# SANCTUARY TARGET TYPES
# Defines what entity is under review
# ============================================================

CONTENT = 'content'            # Any public content (testimony, lesson, moment, etc.)
ACCOUNT = 'account'            # Personal user account
ORGANIZATION = 'organization'  # Church / ministry / organization
MESSENGER_GROUP = 'messenger_group'  # Group chats

REQUEST_TYPE_CHOICES = [
    (CONTENT, 'Content'),
    (ACCOUNT, 'Account'),
    (ORGANIZATION, 'Organization'),
    (MESSENGER_GROUP, 'Messenger Group'),
]
