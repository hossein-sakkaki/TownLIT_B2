# apps/core/ownership/ownership_filters.py

from django.db.models import Q, QuerySet
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

User = get_user_model()


def exclude_owned_by_viewer(qs: QuerySet, viewer) -> QuerySet:
    """
    Exclude content owned by the current viewer.

    Supports GenericForeignKey ownership:
    - Member
    - GuestUser
    - (future-safe for other owner types)

    This is a QUERY-LEVEL filter (pre-fetch).
    Must NOT raise, must NOT leak, must stay silent.
    """

    # -------------------------------------------------
    # Anonymous / unauthenticated viewers
    # -------------------------------------------------
    if not viewer or not viewer.is_authenticated:
        return qs

    owner_filters: list[Q] = []

    # -------------------------------------------------
    # Member-owned content
    # -------------------------------------------------
    member = getattr(viewer, "member_profile", None)
    if member:
        owner_filters.append(
            Q(
                content_type=ContentType.objects.get_for_model(
                    member.__class__,
                    for_concrete_model=False,
                ),
                object_id=member.id,
            )
        )

    # -------------------------------------------------
    # GuestUser-owned content
    # -------------------------------------------------
    guest = getattr(viewer, "guest_profile", None)
    if guest:
        owner_filters.append(
            Q(
                content_type=ContentType.objects.get_for_model(
                    guest.__class__,
                    for_concrete_model=False,
                ),
                object_id=guest.id,
            )
        )

    # -------------------------------------------------
    # Nothing to exclude
    # -------------------------------------------------
    if not owner_filters:
        return qs

    # -------------------------------------------------
    # Combine ownership filters (OR)
    # -------------------------------------------------
    combined_filter = owner_filters[0]
    for extra in owner_filters[1:]:
        combined_filter |= extra

    return qs.exclude(combined_filter)
