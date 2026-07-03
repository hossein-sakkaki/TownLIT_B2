# apps/profiles/services/profile_migration_content_safety.py

import logging

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.core.visibility.constants import (
    VISIBILITY_COVENANT,
    VISIBILITY_PRIVATE,
)
from apps.posts.models.moment import Moment

logger = logging.getLogger(__name__)


def privatize_member_covenant_moments_before_guest_migration(member) -> int:
    """
    When a Member migrates to GuestUser, Guest profile does not support
    LITCovenant visibility.

    To keep content safe and editable, all Member-owned Moments that are
    currently visible only to LITCovenant are changed to Only Me before
    Moment ownership is moved to GuestUser.

    Returns:
        Number of updated Moments.
    """
    if not member:
        return 0

    member_ct = ContentType.objects.get_for_model(
        member.__class__,
        for_concrete_model=False,
    )

    updated = (
        Moment.objects
        .filter(
            content_type=member_ct,
            object_id=member.id,
            visibility=VISIBILITY_COVENANT,
        )
        .update(
            visibility=VISIBILITY_PRIVATE,
            updated_at=timezone.now(),
        )
    )

    return updated