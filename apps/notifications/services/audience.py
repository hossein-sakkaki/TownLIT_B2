# apps/notifications/services/audience.py

from __future__ import annotations

from django.contrib.auth import (
    get_user_model,
)
from django.db.models import Q

from apps.profiles.constants import (
    ACCEPTED,
)
from apps.profiles.models import (
    Friendship,
)


User = get_user_model()


def accepted_friend_users(user):
    """
    Return active accepted friends for one user.

    Shared by publication notification producers such as
    Moment and Journey.
    """

    if not user or not getattr(
        user,
        "pk",
        None,
    ):
        return User.objects.none()

    outgoing_ids = (
        Friendship.objects
        .filter(
            from_user=user,
            status=ACCEPTED,
            is_active=True,
        )
        .values_list(
            "to_user_id",
            flat=True,
        )
    )

    incoming_ids = (
        Friendship.objects
        .filter(
            to_user=user,
            status=ACCEPTED,
            is_active=True,
        )
        .values_list(
            "from_user_id",
            flat=True,
        )
    )

    return (
        User.objects
        .filter(
            Q(
                pk__in=outgoing_ids
            )
            | Q(
                pk__in=incoming_ids
            ),
            is_active=True,
        )
        .exclude(
            pk=user.pk
        )
        .distinct()
    )