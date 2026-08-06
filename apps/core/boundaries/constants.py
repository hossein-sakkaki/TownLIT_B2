"""
TownLIT Peace & Boundaries constants.

Product language:
- Stillness gives the owner quiet space without ending a relationship.
- Boundary is TownLIT's protective blocking control. It prevents direct
  interaction and hides user-generated content between both users.

Technical note:
Apple App Review may refer to Boundary as "blocking", while TownLIT uses
the softer product-facing name "Boundary".
"""

BOUNDARY_STILLNESS = "stillness"
BOUNDARY_BOUNDARY = "boundary"

BOUNDARY_TYPE_CHOICES = [
    (
        BOUNDARY_STILLNESS,
        "Stillness",
    ),
    (
        BOUNDARY_BOUNDARY,
        "Boundary",
    ),
]

BOUNDARY_TYPE_VALUES = {
    BOUNDARY_STILLNESS,
    BOUNDARY_BOUNDARY,
}


BOUNDARY_SOURCE_PROFILE = "profile"
BOUNDARY_SOURCE_MESSENGER = "messenger"
BOUNDARY_SOURCE_COMMENT = "comment"
BOUNDARY_SOURCE_REACTION = "reaction"
BOUNDARY_SOURCE_SETTINGS = "settings"
BOUNDARY_SOURCE_SANCTUARY = "sanctuary"
BOUNDARY_SOURCE_SYSTEM = "system"

BOUNDARY_SOURCE_CHOICES = [
    (
        BOUNDARY_SOURCE_PROFILE,
        "Profile",
    ),
    (
        BOUNDARY_SOURCE_MESSENGER,
        "Messenger",
    ),
    (
        BOUNDARY_SOURCE_COMMENT,
        "Comment",
    ),
    (
        BOUNDARY_SOURCE_REACTION,
        "Reaction",
    ),
    (
        BOUNDARY_SOURCE_SETTINGS,
        "Settings",
    ),
    (
        BOUNDARY_SOURCE_SANCTUARY,
        "Sanctuary",
    ),
    (
        BOUNDARY_SOURCE_SYSTEM,
        "System",
    ),
]

BOUNDARY_SOURCE_VALUES = {
    value
    for value, _label in BOUNDARY_SOURCE_CHOICES
}


BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE = (
    "Direct interaction is currently unavailable."
)

BOUNDARY_SELF_ACTION_MESSAGE = (
    "You cannot create Stillness or Boundary with yourself."
)