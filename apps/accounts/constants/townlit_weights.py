# apps/accounts/constants/townlit_weights.py

"""
Weights for TownLIT gold badge eligibility.

Rules:
- Hard requirements are checked separately.
- Score is used for initial gold unlock eligibility.
- After gold is granted, score drops alone do NOT revoke the badge.
"""

# Profile maturity signals
BIOGRAPHY_COMPLETED = 3
VISION_COMPLETED = 3
SPIRITUAL_REBIRTH_DAY_COMPLETED = 3
DENOMINATION_BRANCH_COMPLETED = 3

# Activity / participation signals
MOMENT_CREATED = 1
PRAYER_CREATED = 3
TESTIMONY_CREATED = 5
FRIEND_CREATED = 1
ORGANIZATION_MEMBERSHIP = 3
SERVICE_TYPE_SELECTED = 2
SPIRITUAL_GIFTS_COMPLETED = 6

# Activity caps
MAX_MOMENT_SCORE = 15
MAX_PRAYER_SCORE = 20
MAX_TESTIMONY_SCORE = 20
MAX_FRIEND_SCORE = 10
MAX_ORGANIZATION_SCORE = 12
MAX_SERVICE_TYPE_SCORE = 8

# Negative signals
ACCOUNT_REPORT_PENALTY = -15
MAX_REPORT_PENALTY = -60

# Initial gold unlock threshold
TOWNLIT_GOLD_THRESHOLD = 60