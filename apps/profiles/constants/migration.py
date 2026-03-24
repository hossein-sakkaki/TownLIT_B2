# apps/profiles/constants/migration.py

from django.utils.translation import gettext_lazy as _

# Profile migration types
GUEST_TO_MEMBER = "guest_to_member"
MEMBER_TO_GUEST = "member_to_guest"

MIGRATION_CHOICES = [
    (GUEST_TO_MEMBER, _("GuestUser to Member")),
    (MEMBER_TO_GUEST, _("Member to GuestUser")),
]
