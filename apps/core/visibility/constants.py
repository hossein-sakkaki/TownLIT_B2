# apps/core/visibility/constants.py

# -------------------------
# Visibility Levels
# -------------------------
VISIBILITY_GLOBAL = "global"        # public
VISIBILITY_FRIENDS = "friends"      # friends only
VISIBILITY_COVENANT = "covenant"    # LIT Covenant
VISIBILITY_PRIVATE = "private"      # only me

VISIBILITY_CHOICES = [
    (VISIBILITY_GLOBAL, "Global (Public)"),
    (VISIBILITY_FRIENDS, "Friends only"),
    (VISIBILITY_COVENANT, "LIT Covenant"),
    (VISIBILITY_PRIVATE, "Only me"),
]
