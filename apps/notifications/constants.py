# apps/notifications/constants.py

from enum import Enum

class NotificationVerb(str, Enum):
    REACT = "react"
    COMMENT = "comment"
    REPLY = "reply"

# Flat, stable types (good for analytics & prefs)
NOTIFICATION_TYPES = [
    # --- Content Interactions ---
    ("new_comment", "New Comment"),
    ("new_reply", "New Reply"),
    ("new_reply_post_owner", "Reply to Post Comment"),

    # --- Reactions ---
    ("new_reaction", "New Reaction"),
    ("new_reaction_bless", "Bless Reaction"),
    ("new_reaction_gratitude", "Gratitude Reaction"),
    ("new_reaction_amen", "Amen Reaction"),
    ("new_reaction_encouragement", "Encouragement Reaction"),
    ("new_reaction_empathy", "Empathy Reaction"),

    # --- Friendships ---
    ("friend_request_received", "Friend Request Received"),
    ("friend_request_accepted", "Friend Request Accepted"),
    ("friend_request_declined", "Friend Request Declined"),
    ("friend_request_cancelled", "Friend Request Cancelled"),
    ("friendship_deleted", "Friendship Deleted"),  

    # --- Fellowships ---
    ("fellowship_request_received", "Fellowship Request Received"),
    ("fellowship_request_accepted", "Fellowship Request Accepted"),
    ("fellowship_request_confirmed", "Fellowship Relationship Confirmed"),
    ("fellowship_request_declined", "Fellowship Request Declined"),
    ("fellowship_decline_notice", "Fellowship Decline Notice"),
    ("fellowship_cancelled", "Fellowship Cancelled"),
]



# Notification Channels ----------------------------------------------------
CHANNEL_PUSH = 1     # FCM
CHANNEL_WS = 2       # WebSocket
CHANNEL_EMAIL = 4    # Email
CHANNEL_DEFAULT = CHANNEL_PUSH | CHANNEL_WS | CHANNEL_EMAIL
