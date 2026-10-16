# apps/conversation/constants/groups.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

FOUNDER = "founder"
ELDER = "elder"
PARTICIPANT = "participant"

GROUP_ROLE_CHOICES = [
    (FOUNDER, "Founder"),
    (ELDER, "Elder"),
    (PARTICIPANT, "Participant"),
]

JOINED = "joined"
LEFT = "left"
REMOVED = "removed"
FOUNDER_TRANSFERRED = "founder_transferred"
PROMOTED_TO_ELDER = "promoted_to_elder"
DEMOTED_TO_PARTICIPANT = "demoted_to_participant"
GROUP_DELETED = "group_deleted"
RESIGNED_FROM_ELDER = "resigned_from_elder"

SYSTEM_MESSAGE_EVENT_CHOICES = [
    (JOINED, "Joined"),
    (LEFT, "Left"),
    (REMOVED, "Removed"),
    (FOUNDER_TRANSFERRED, "Founder Transferred"),
    (PROMOTED_TO_ELDER, "Promoted to Elder"),
    (DEMOTED_TO_PARTICIPANT, "Demoted to Participant"),
    (GROUP_DELETED, "Group Deleted"),
    (RESIGNED_FROM_ELDER, "Resigned from Elder Role"),
]
