# apps/notifications/signals/reaction_signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.posts.models import Reaction
from utils.common.utils import send_push_notification
import logging

logger = logging.getLogger(__name__)

try:
    from apps.notifications.models import Notification
except Exception:
    Notification = None
    logger.warning("⚠️ Notification model not available — skipping DB notification creation.")


# --- Helper to safely build a message based on reaction type ---
def _reaction_message(username: str, reaction_type: str) -> str:
    mapping = {
        "bless": f"{username} sent you a blessing.",
        "gratitude": f"{username} expressed gratitude.",
        "amen": f"{username} said Amen to your post.",
        "encouragement": f"{username} sent you encouragement.",
        "empathy": f"{username} expressed empathy.",
    }
    return mapping.get(reaction_type, f"{username} reacted to your post.")


# -----------------------------------------------------------------
# 1️⃣ Standard DB Notification (safe if notifications not yet active)
# -----------------------------------------------------------------
@receiver(post_save, sender=Reaction)
def create_reaction_notification(sender, instance, created, **kwargs):
    if not created or Notification is None:
        return

    try:
        content_object = getattr(instance, "content_object", None)
        to_user = getattr(content_object, "user", None)
        if not to_user:
            return  # skip if no valid user target

        # Build safe link
        try:
            link = content_object.get_absolute_url()
        except Exception:
            link = None

        message = _reaction_message(instance.name.username, instance.reaction_type)
        notification_type = f"new_{instance.reaction_type}"

        Notification.objects.create(
            user=to_user,
            message=message,
            notification_type=notification_type,
            content_type=ContentType.objects.get_for_model(sender),
            object_id=instance.id,
            link=link,
        )

    except Exception as e:
        logger.warning(f"⚠️ Skipped DB notification for Reaction id={instance.id}: {e}")


# -----------------------------------------------------------------
# 2️⃣ Push Notification (Firebase / FCM)
# -----------------------------------------------------------------
@receiver(post_save, sender=Reaction)
def send_reaction_push_notification(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        content_object = getattr(instance, "content_object", None)
        to_user = getattr(content_object, "user", None)
        if not to_user or not getattr(to_user, "registration_id", None):
            return  # no push token, skip

        message = _reaction_message(instance.name.username, instance.reaction_type)

        send_push_notification(
            registration_id=to_user.registration_id,
            message_title="New Reaction",
            message_body=message,
        )
        logger.info(f"✅ Push notification queued to user {to_user.id}: {message}")

    except Exception as e:
        logger.warning(f"⚠️ Skipped push notification for Reaction id={instance.id}: {e}")


# -----------------------------------------------------------------
# 3️⃣ Real-Time Notification (Channels / WebSocket)
# -----------------------------------------------------------------
@receiver(post_save, sender=Reaction)
def send_reaction_real_time_notification(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        content_object = getattr(instance, "content_object", None)
        to_user = getattr(content_object, "user", None)
        if not to_user:
            return

        message = _reaction_message(instance.name.username, instance.reaction_type)

        async_to_sync(channel_layer.group_send)(
            f"user_{to_user.id}",
            {"type": "send_notification", "message": message},
        )
        logger.info(f"💬 Real-time notification sent to user {to_user.id}: {message}")

    except Exception as e:
        logger.warning(f"⚠️ Skipped real-time notification for Reaction id={instance.id}: {e}")
