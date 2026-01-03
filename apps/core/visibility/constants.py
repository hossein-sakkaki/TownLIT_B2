# apps/core/visibility/constants.py

# -------------------------
# Visibility Levels
# -------------------------
VISIBILITY_DEFAULT = "default"      # follow profile privacy
VISIBILITY_GLOBAL = "global"        # public even if profile is private
VISIBILITY_FRIENDS = "friends"      # friends only
VISIBILITY_COVENANT = "covenant"    # LITCovenant / Fellowship
VISIBILITY_PRIVATE = "private"      # only me

VISIBILITY_CHOICES = [
    (VISIBILITY_DEFAULT, "Default (Profile-based)"),
    (VISIBILITY_GLOBAL, "Global (Public)"),
    (VISIBILITY_FRIENDS, "Friends only"),
    (VISIBILITY_COVENANT, "LIT Covenant"),
    (VISIBILITY_PRIVATE, "Only me"),
]
