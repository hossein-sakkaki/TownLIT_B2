# apps/notifications/signals/reaction_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.posts.models import Reaction
from apps.notifications.services import create_and_dispatch_notification

# Map reaction -> message/type
def _reaction_message(username: str, rtype: str) -> tuple[str, str]:
    mapping = {
        "bless": (f"{username} sent you a blessing.", "new_reaction"),
        "gratitude": (f"{username} expressed gratitude.", "new_reaction"),
        "amen": (f"{username} said Amen to your post.", "new_reaction"),
        "encouragement": (f"{username} encouraged your post.", "new_reaction"),
        "empathy": (f"{username} expressed empathy.", "new_reaction"),
    }
    return mapping.get(rtype, (f"{username} reacted to your post.", "new_reaction"))

def _resolve_owner(obj):
    # Try common owner fields
    for attr in ("user", "owner", "author", "created_by", "name"):
        v = getattr(obj, attr, None)
        if v is not None and hasattr(v, "id"):
            return v
    return None

@receiver(post_save, sender=Reaction, dispatch_uid="notif_on_reaction_create_v1")
def on_reaction_created(sender, instance: Reaction, created, **kwargs):
    if not created:
        return

    content_object = getattr(instance, "content_object", None)
    to_user = _resolve_owner(content_object)
    actor = getattr(instance, "name", None)  # your model uses "name" as FK to CustomUser

    if not to_user or not actor or to_user.id == actor.id:
        return  # Skip self-notify or invalid targets

    # Build link safely if available
    link = None
    try:
        if hasattr(content_object, "get_absolute_url"):
            link = content_object.get_absolute_url()
    except Exception:
        pass

    msg, notif_type = _reaction_message(actor.username, instance.reaction_type)

    # Target = the reacted object; Action = Reaction row
    create_and_dispatch_notification(
        recipient=to_user,
        actor=actor,
        notif_type=notif_type,
        message=msg,
        target_obj=content_object,
        action_obj=instance,
        link=link,
    )
