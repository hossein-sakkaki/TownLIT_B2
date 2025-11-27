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

    # --- Messages ---
    ("new_message_direct", "New Direct Message"),
    ("new_message_group", "New Group Message"),
]



# Notification Channels ----------------------------------------------------
CHANNEL_PUSH = 1     # FCM
CHANNEL_WS = 2       # WebSocket
CHANNEL_EMAIL = 4    # Email
CHANNEL_DEFAULT = CHANNEL_PUSH | CHANNEL_WS | CHANNEL_EMAIL


# Notification Preferences Metadata ----------------------------------------
NOTIFICATION_PREF_METADATA = {
    # ------------------------
    # COMMENTS
    # ------------------------
    "new_comment": {
        "category": "Comments",
        "label": "New comment on your post",
        "description": "You will be notified when another user writes a new comment on a post you created.",
    },
    "new_reply": {
        "category": "Comments",
        "label": "New reply to your comment",
        "description": "You will be notified when someone replies directly to your comment.",
    },
    "new_reply_post_owner": {
        "category": "Comments",
        "label": "New reply on a comment under your post",
        "description": "You will be notified when a reply is added to a comment under a post you created.",
    },

    # ------------------------
    # REACTIONS
    # ------------------------
    "new_reaction": {
        "category": "Reactions",
        "label": "New reaction on your post",
        "description": "You will receive a notification when someone reacts to your post.",
    },
    "new_reaction_bless": {
        "category": "Reactions",
        "label": "Bless reaction",
        "description": "Notifies you when someone reacts with 'Bless' to your post.",
    },
    "new_reaction_gratitude": {
        "category": "Reactions",
        "label": "Gratitude reaction",
        "description": "Notifies you when someone reacts with 'Gratitude' to your post.",
    },
    "new_reaction_amen": {
        "category": "Reactions",
        "label": "Amen reaction",
        "description": "Notifies you when someone reacts with 'Amen' to your post.",
    },
    "new_reaction_encouragement": {
        "category": "Reactions",
        "label": "Encouragement reaction",
        "description": "Notifies you when someone reacts with 'Encouragement' to your post.",
    },
    "new_reaction_empathy": {
        "category": "Reactions",
        "label": "Empathy reaction",
        "description": "Notifies you when someone reacts with 'Empathy' to your post.",
    },

    # ------------------------
    # FRIENDSHIPS
    # ------------------------
    "friend_request_received": {
        "category": "Friendships",
        "label": "New friend request",
        "description": "You will be notified when someone sends you a friend request.",
    },
    "friend_request_accepted": {
        "category": "Friendships",
        "label": "Friend request accepted",
        "description": "You will be notified when someone accepts your friend request.",
    },
    "friend_request_declined": {
        "category": "Friendships",
        "label": "Friend request declined",
        "description": "You will be notified when someone declines your friend request.",
    },
    "friend_request_cancelled": {
        "category": "Friendships",
        "label": "Friend request cancelled",
        "description": "You will be notified if a user cancels a friend request they had sent you.",
    },
    "friendship_deleted": {
        "category": "Friendships",
        "label": "Removed from friends",
        "description": "You will be notified if someone removes you from their friend list.",
    },

    # ------------------------
    # LITCovenant (Fellowships)
    # ------------------------
    "fellowship_request_received": {
        "category": "LITCovenant",
        "label": "New LITCovenant request",
        "description": "You will be notified when someone sends you a LITCovenant request.",
    },
    "fellowship_request_accepted": {
        "category": "LITCovenant",
        "label": "LITCovenant request accepted",
        "description": "You will be notified when someone accepts your LITCovenant request.",
    },
    "fellowship_request_confirmed": {
        "category": "LITCovenant",
        "label": "LITCovenant relationship confirmed",
        "description": "You will be notified when a mutual LITCovenant relationship is confirmed.",
    },
    "fellowship_request_declined": {
        "category": "LITCovenant",
        "label": "LITCovenant request declined",
        "description": "You will be notified when someone declines your LITCovenant request.",
    },
    "fellowship_decline_notice": {
        "category": "LITCovenant",
        "label": "LITCovenant decline notice",
        "description": "You will be notified when someone indicates they cannot accept your LITCovenant request.",
    },
    "fellowship_cancelled": {
        "category": "LITCovenant",
        "label": "LITCovenant cancelled",
        "description": "You will be notified when a LITCovenant relationship is cancelled.",
    },

    # ------------------------
    # MESSAGES
    # ------------------------
    "new_message_direct": {
        "category": "Messages",
        "label": "New direct message",
        "description": "You will be notified when someone sends you a direct message.",
    },
    "new_message_group": {
        "category": "Messages",
        "label": "New group message",
        "description": "You will be notified when someone sends a new message in a group you are part of.",
    },


}
