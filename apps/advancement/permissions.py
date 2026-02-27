# apps/advancement/permissions.py

from django.contrib.auth.models import Group


ADVANCEMENT_OFFICER_GROUP = "AdvancementOfficer"
BOARD_VIEWER_GROUP = "BoardViewer"


def user_in_group(user, group_name: str) -> bool:
    """Check if user belongs to a named group."""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


def is_advancement_officer(user) -> bool:
    """Officer can manage records."""
    return bool(user and user.is_authenticated and (
        user.is_superuser or user_in_group(user, ADVANCEMENT_OFFICER_GROUP)
    ))


def is_board_viewer(user) -> bool:
    """Board viewer can access read-only dashboard/admin."""
    return bool(user and user.is_authenticated and (
        user.is_superuser
        or user_in_group(user, ADVANCEMENT_OFFICER_GROUP)
        or user_in_group(user, BOARD_VIEWER_GROUP)
    ))


def ensure_advancement_groups():
    """Create default groups safely (can be called from shell or migration hook)."""
    Group.objects.get_or_create(name=ADVANCEMENT_OFFICER_GROUP)
    Group.objects.get_or_create(name=BOARD_VIEWER_GROUP)