from .models import ReviewLog
from django.contrib.contenttypes.models import ContentType

def create_review_log(admin_user, target_instance, action_text, comment=""):
    content_type = ContentType.objects.get_for_model(target_instance.__class__)
    ReviewLog.objects.create(
        admin=admin_user,
        content_type=content_type,
        object_id=target_instance.id,
        action=action_text,
        comment=comment,
    )