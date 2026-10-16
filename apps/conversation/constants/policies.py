# apps/conversation/constants/policies.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

SOFT_DELETE = "soft_delete_for_user"
LEAVE_GROUP_SOFT_DELETE = "leave_group_and_soft_delete"

DELETE_POLICY_CHOICES = [
    ("SOFT_DELETE", "Soft Delete for User"),
    ("LEAVE_GROUP_SOFT_DELETE", "Leave Group & Soft Delete"),
]

DELETE_AFTER_VIEW = "delete_after_view"
KEEP = "keep"

MESSAGE_POLICY_CHOICES = [
    (DELETE_AFTER_VIEW, "Delete After View"),
    (KEEP, "Keep Message"),
]
