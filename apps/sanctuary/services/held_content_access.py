# apps/sanctuary/services/held_content_access.py

from __future__ import annotations

from functools import lru_cache

from django.contrib.contenttypes.models import ContentType

from apps.sanctuary.models import SanctuarySafetyHold
from apps.sanctuary.services.admin_pool import sanctuary_admin_queryset


HELD_CONTENT_MESSAGE = (
    "This content is temporarily unavailable while a Sanctuary review "
    "is in progress."
)


@lru_cache(maxsize=32)
def _content_type_id(app_label: str, model: str) -> int | None:
    try:
        return ContentType.objects.get(
            app_label__iexact=app_label,
            model__iexact=model,
        ).pk
    except ContentType.DoesNotExist:
        return None


def is_sanctuary_review_admin(user) -> bool:
    """
    Return True only for users permitted to inspect Sanctuary cases.

    Superusers are always permitted. Regular TownLIT admins must belong
    to the canonical sanctuary_admin pool.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    try:
        return sanctuary_admin_queryset().filter(pk=user.pk).exists()
    except Exception:
        return False


def active_safety_hold_for(target) -> SanctuarySafetyHold | None:
    hold_target = resolve_sanctuary_hold_target(target)

    if hold_target is None or not getattr(hold_target, "pk", None):
        return None

    try:
        content_type = ContentType.objects.get_for_model(
            hold_target.__class__,
            for_concrete_model=False,
        )
    except Exception:
        return None

    return (
        SanctuarySafetyHold.objects
        .filter(
            content_type=content_type,
            object_id=hold_target.pk,
            status=SanctuarySafetyHold.STATUS_ACTIVE,
            ended_at__isnull=True,
        )
        .only("id", "status", "applied_at")
        .first()
    )


def is_under_active_safety_hold(target) -> bool:
    return active_safety_hold_for(target) is not None


def can_inspect_held_content(*, viewer, target) -> bool:
    """
    Only Sanctuary review admins may receive original held content/media.

    The owner receives hold status through the Sanctuary target-status
    endpoint but does not receive the held media itself.
    """
    if not is_under_active_safety_hold(target):
        return True

    return is_sanctuary_review_admin(viewer)


def held_asset_field_is_allowed(target, field_name: str) -> bool:
    """
    Limit privileged inspection to known media fields.

    This prevents an admin from requesting arbitrary model file fields
    through the generic Asset Delivery endpoint.
    """
    if target is None:
        return False

    try:
        key = (
            target._meta.app_label.lower(),
            target._meta.model_name.lower(),
        )
    except Exception:
        return False

    field_name = str(field_name or "").strip()

    allowed_fields = {
        ("posts", "moment"): {
            "image",
            "video",
            "thumbnail",
            "cover_image",
        },
        ("posts", "prayer"): {
            "image",
            "video",
            "thumbnail",
        },
        ("posts", "prayerresponse"): {
            "image",
            "video",
            "thumbnail",
        },
        ("posts", "testimony"): {
            "audio",
            "video",
            "thumbnail",
            "audio_artwork",
        },
        ("posts", "journeyentry"): {
            "rendered_image",
            "thumbnail",
        },
    }

    if key == ("posts", "moment") and field_name.startswith("image_items:"):
        return True

    return field_name in allowed_fields.get(key, set())


def held_representation_or_none(*, target, viewer, data):
    """
    Suppress serialized held content for every non-Sanctuary-admin viewer.

    This closes direct serializer/CDN-key leakage even when a view retrieves
    the object by ID or slug without applying the normal active queryset.
    """
    if not is_under_active_safety_hold(target):
        return data

    if is_sanctuary_review_admin(viewer):
        return data

    return None


def resolve_sanctuary_hold_target(target):
    """
    Resolve the object whose Sanctuary hold governs delivery.

    PrayerResponse inherits the moderation state of its parent Prayer.
    Other supported targets govern themselves.
    """
    if target is None:
        return None

    try:
        if target._meta.label_lower == "posts.prayerresponse":
            return target.prayer
    except Exception:
        return None

    return target