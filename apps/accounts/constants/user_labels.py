# apps/accounts/constants/user_labels.py

"""
User faith / onboarding path label choices.

Important:
- BELIEVER / SEEKER / PREFER_NOT_TO_SAY are active onboarding paths.
- YOUNG_PATH is intentionally exposed to clients as a coming-soon option,
  but it is NOT an active profile path yet.
"""

BELIEVER = "believer"
SEEKER = "seeker"
PREFER_NOT_TO_SAY = "prefer_not_to_say"

# Future protected account path.
# This must not create a profile until the child/youth account system is ready.
YOUNG_PATH = "young_path"

USER_LABEL_CHOICES = [
    (BELIEVER, "I follow Jesus (Believer)"),
    (SEEKER, "I’m exploring faith (Seeker)"),
    (PREFER_NOT_TO_SAY, "I’d prefer not to say"),
    (YOUNG_PATH, "TownLIT Young Path — Coming Soon"),
]

ACTIVE_USER_LABEL_KEYS = {
    BELIEVER,
    SEEKER,
    PREFER_NOT_TO_SAY,
}

UNAVAILABLE_USER_LABEL_KEYS = {
    YOUNG_PATH,
}

# Minimum age for a standard TownLIT account.
# Younger protected accounts are planned but not available yet.
MIN_STANDARD_ACCOUNT_AGE = 13

YOUNG_PATH_COMING_SOON_MESSAGE = (
    "TownLIT Young Path is coming soon. Protected accounts for younger members "
    "are not available yet. We are working carefully on this experience so it "
    "can be safe, age-appropriate, and aligned with privacy expectations."
)

UNDER_MINIMUM_STANDARD_ACCOUNT_AGE_MESSAGE = (
    "TownLIT standard accounts are currently available for users age 13 and older. "
    "Protected younger accounts are coming soon. If this birthday is incorrect, "
    "please enter your correct birthday. If you are under 13, please wait until "
    "TownLIT Young Path becomes available."
)