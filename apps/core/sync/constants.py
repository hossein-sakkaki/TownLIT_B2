# apps/core/sync/constants.py

class SyncOperation:
    UPSERT = "upsert"
    DELETE = "delete"
    REMOVE = "remove"


class SyncReason:
    DELETED = "deleted"
    VISIBILITY_CHANGED = "visibility_changed"
    PERMISSION_REVOKED = "permission_revoked"
    BLOCKED = "blocked"
    MEMBERSHIP_CHANGED = "membership_changed"
    MODERATION_ACTION = "moderation_action"


class SyncScope:
    CONVERSATION_DIALOGUES = "conversation.dialogues"
    CONVERSATION_MESSAGES = "conversation.messages"

    PROFILE_SNAPSHOT = "profiles.snapshot"

    STREAM_FEED = "stream.feed"
    MOMENTS_FEED = "moments.feed"

    MEDIA_METADATA = "media.metadata"

    STORE_PRODUCTS = "store.products"
    STORE_CART = "store.cart"
    STORE_ORDERS = "store.orders"


SYNC_TOKEN_HEADER = "X-TownLIT-Sync-Token"
SERVER_TIME_HEADER = "X-TownLIT-Server-Time" 