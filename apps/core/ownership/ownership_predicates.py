# apps/core/ownership/ownership_predicates.py

from django.db.models import Q
from django.contrib.contenttypes.models import ContentType


def owner_q_for_user_ids(*, user_ids: list[int]) -> Q:
    """
    Build a Q expression matching content owned by users in `user_ids`.

    Supports:
    - Member-owned content
    - GuestUser-owned content

    Returns a PURE Q predicate.
    Caller decides filter() / exclude().
    """
    if not user_ids:
        # Safe empty predicate
        return Q(pk__in=[])

    from apps.profiles.models import Member, GuestUser

    member_ct = ContentType.objects.get_for_model(Member)
    guest_ct = ContentType.objects.get_for_model(GuestUser)

    member_ids = Member.objects.filter(
        user_id__in=user_ids
    ).values_list("id", flat=True)

    guest_ids = GuestUser.objects.filter(
        user_id__in=user_ids
    ).values_list("id", flat=True)

    return (
        Q(content_type=member_ct, object_id__in=member_ids)
        | Q(content_type=guest_ct, object_id__in=guest_ids)
    )
