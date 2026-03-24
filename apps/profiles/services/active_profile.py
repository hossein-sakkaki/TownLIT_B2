# apps/profiles/services/active_profile.py

from dataclasses import dataclass
from typing import Optional

from apps.profiles.models.member import Member
from apps.profiles.models.guest import GuestUser


@dataclass
class ActiveProfileResult:
    profile_type: Optional[str]
    member: Optional[Member] = None
    guest: Optional[GuestUser] = None

    @property
    def profile(self):
        return self.member or self.guest


def get_active_profile(user) -> ActiveProfileResult:
    """Resolve the active profile for a user."""
    member = getattr(user, "member_profile", None)
    if member and member.is_active:
        return ActiveProfileResult(
            profile_type="member",
            member=member,
            guest=None,
        )

    guest = getattr(user, "guest_profile", None)
    if guest and guest.is_active:
        return ActiveProfileResult(
            profile_type="guest",
            member=None,
            guest=guest,
        )

    return ActiveProfileResult(
        profile_type=None,
        member=None,
        guest=None,
    )