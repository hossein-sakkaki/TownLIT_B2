# apps/sanctuary/constants/fast_track.py
# ============================================================
# ADMIN FAST-TRACK CASES
# Immediate admin review, no council
# ============================================================

from .targets import CONTENT, ACCOUNT, ORGANIZATION, MESSENGER_GROUP
from .reasons import *

ADMIN_FAST_TRACK = {
    CONTENT: [
        SEXUALLY_INAPPROPRIATE_CONTENT,
        TERRORIST_CONTENT,
        INTELLECTUAL_PROPERTY_VIOLATION,
        VIOLENT_CONTENT,
    ],
    ACCOUNT: [
        FRAUD,
        FAKE_IDENTITY,
        ILLEGAL_ACTIVITIES,
    ],
    ORGANIZATION: [
        MISMANAGEMENT_OF_FUNDS,
        MISUSE_OF_DONATIONS,
    ],
    MESSENGER_GROUP: [
        COORDINATED_ATTACK,
        UNSAFE_ENVIRONMENT,
    ],
}
