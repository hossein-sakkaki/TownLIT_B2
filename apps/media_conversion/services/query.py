# apps/media_conversion/services/query.py

from django.db.models import QuerySet, Q

def exclude_unready_media(
    qs: QuerySet,
    *,
    ready_field: str = "is_converted",
) -> QuerySet:
    """
    HARD domain rule:
    Any object with media pipeline must be converted before public exposure.
    """
    return qs.exclude(
        Q(**{ready_field: False})
    )
