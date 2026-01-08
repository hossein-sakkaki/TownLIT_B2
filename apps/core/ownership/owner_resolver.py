import logging
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)


def resolve_owner_object_from_gfk(obj):
    """
    Resolve content owner object from GenericForeignKey.
    Returns model instance or None.
    """
    try:
        ct = obj.content_type
        if not ct or not obj.object_id:
            return None

        model_cls = ct.model_class()
        if not model_cls:
            return None

        return model_cls.objects.filter(pk=obj.object_id).first()
    except Exception:
        logger.exception("Failed to resolve owner object from GFK")
        return None


def resolve_owner_user_and_member(obj):
    """
    Normalize owner into:
    - owner_user: CustomUser | None
    - owner_member: Member | None
    - owner_obj: raw resolved object
    """
    owner_obj = resolve_owner_object_from_gfk(obj)
    if not owner_obj:
        return None, None, None

    # Case A: owner is Member
    if hasattr(owner_obj, "user"):
        return owner_obj.user, owner_obj, owner_obj

    # Case B: owner is CustomUser
    try:
        from apps.accounts.models import CustomUser
        if isinstance(owner_obj, CustomUser):
            owner_user = owner_obj
            owner_member = getattr(owner_user, "member_profile", None)
            return owner_user, owner_member, owner_obj
    except Exception:
        logger.exception("CustomUser resolution failed")

    # Other owner types (Organization, GuestUser, ...)
    return None, None, owner_obj
