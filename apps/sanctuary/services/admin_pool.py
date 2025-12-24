from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

SANCTUARY_ADMIN_GROUP = "sanctuary_admin"


def sanctuary_admin_queryset(*, language: str | None = None):
    """
    Pool of admins allowed to handle Sanctuary cases.

    Current policy:
      - is_admin=True  (stored field)
      - in group 'sanctuary_admin'
      - active / not deleted / not suspended
    """
    qs = User.objects.filter(
        is_admin=True,
        groups__name=SANCTUARY_ADMIN_GROUP,
        is_active=True,
        is_deleted=False,
        is_suspended=False,
    ).distinct()

    # Optional: language match (future-friendly)
    if language:
        qs = qs.filter(Q(primary_language=language) | Q(secondary_language=language))

    return qs
