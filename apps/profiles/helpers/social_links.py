# apps/profiles/helpers/social_links.py

from django.contrib.contenttypes.models import ContentType

from apps.accounts.models.user import CustomUser
from apps.accounts.models.social import SocialMediaLink


def social_links_for_user(user: CustomUser):
    """
    Generic FK: content_object = CustomUser
    """
    ct = ContentType.objects.get_for_model(type(user))
    return (
        SocialMediaLink.objects
        .filter(content_type=ct, object_id=user.id, is_active=True)
        .select_related("social_media_type")
        .order_by("id")
    )