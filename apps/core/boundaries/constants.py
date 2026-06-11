# apps/core/boundaries/constants.py

"""
Peace & Boundaries constants.

TownLIT does not frame this as rejection or revenge.
Stillness gives quiet space.
Boundary pauses direct interaction for protection and peace.
"""

BOUNDARY_STILLNESS = "stillness"
BOUNDARY_BOUNDARY = "boundary"

BOUNDARY_TYPE_CHOICES = [
    (BOUNDARY_STILLNESS, "Stillness"),
    (BOUNDARY_BOUNDARY, "Boundary"),
]

BOUNDARY_SOURCE_PROFILE = "profile"
BOUNDARY_SOURCE_MESSENGER = "messenger"
BOUNDARY_SOURCE_COMMENT = "comment"
BOUNDARY_SOURCE_REACTION = "reaction"
BOUNDARY_SOURCE_SETTINGS = "settings"
BOUNDARY_SOURCE_SANCTUARY = "sanctuary"
BOUNDARY_SOURCE_SYSTEM = "system"

BOUNDARY_SOURCE_CHOICES = [
    (BOUNDARY_SOURCE_PROFILE, "Profile"),
    (BOUNDARY_SOURCE_MESSENGER, "Messenger"),
    (BOUNDARY_SOURCE_COMMENT, "Comment"),
    (BOUNDARY_SOURCE_REACTION, "Reaction"),
    (BOUNDARY_SOURCE_SETTINGS, "Settings"),
    (BOUNDARY_SOURCE_SANCTUARY, "Sanctuary"),
    (BOUNDARY_SOURCE_SYSTEM, "System"),
]

BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE = "This interaction is currently unavailable."
BOUNDARY_SELF_ACTION_MESSAGE = "You cannot create a boundary with yourself."