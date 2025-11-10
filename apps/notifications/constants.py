# apps/notifications/constants.py

from enum import Enum

class NotificationVerb(str, Enum):
    REACT = "react"
    COMMENT = "comment"
    REPLY = "reply"

# Flat, stable types (good for analytics & prefs)
NOTIFICATION_TYPES = (
    ("new_reaction", "New Reaction"),
    ("new_comment", "New Comment"),
    ("new_reply", "New Reply"),
)


# Notification Channels ----------------------------------------------------
CHANNEL_PUSH = 1     # FCM
CHANNEL_WS = 2       # WebSocket
CHANNEL_EMAIL = 4    # Email
CHANNEL_DEFAULT = CHANNEL_PUSH | CHANNEL_WS | CHANNEL_EMAIL
