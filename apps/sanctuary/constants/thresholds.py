# apps/sanctuary/constants/thresholds.py

# ============================================================
# SANCTUARY THRESHOLDS – Policy Configuration
# Version: v1.0
# Purpose:
#   - Define when Sanctuary councils are formed
#   - Define admin fast-track entry points
# ============================================================


# ------------------------------------------------------------
# Council formation thresholds
# ------------------------------------------------------------

COUNCIL_THRESHOLD = {
    'content': 5,            # Public content (posts, testimonies, etc.)
    'account': 7,            # Personal user accounts
    'messenger_group': 6,    # Group chats
    'organization': 9,       # Churches / organizations
}


# ------------------------------------------------------------
# Admin fast-track thresholds
# (Immediate risk – human review required)
# ------------------------------------------------------------

ADMIN_FAST_TRACK_THRESHOLD = {
    'content': 1,            # Severe cases only
    'account': 2,            # Identity-impacting
    'messenger_group': 2,    # Network harm
    'organization': 3,       # Collective risk
}

