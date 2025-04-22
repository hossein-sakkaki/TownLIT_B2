from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.urls import reverse
from apps.notifications.models import Notification
from apps.posts.models import Reaction
from utils.common.utils import send_push_notification
import logging

logger = logging.getLogger(__name__)



# Standard Notification for new reaction
@receiver(post_save, sender=Reaction)
def create_reaction_notification(sender, instance, created, **kwargs):
    if created:
        notification_type = None
        message = None

        if instance.reaction_type == 'bless':
            notification_type = 'new_bless'
            message = f"{instance.name.username} sent you a blessing."
        elif instance.reaction_type == 'gratitude':
            notification_type = 'new_gratitude'
            message = f"{instance.name.username} expressed gratitude."
        elif instance.reaction_type == 'amen':
            notification_type = 'new_amen'
            message = f"{instance.name.username} said Amen to your post."
        elif instance.reaction_type == 'encouragement':
            notification_type = 'new_encouragement'
            message = f"{instance.name.username} sent you encouragement."
        elif instance.reaction_type == 'empathy':
            notification_type = 'new_empathy'
            message = f"{instance.name.username} expressed empathy."

        content_object = instance.content_object
        link = content_object.get_absolute_url()

        if notification_type:
            Notification.objects.create(
                user=content_object.user,
                message=message,
                notification_type=notification_type,
                content_type=ContentType.objects.get_for_model(sender),
                object_id=instance.id,
                link=link
            )

# Push Notification for new reaction
@receiver(post_save, sender=Reaction)
def send_reaction_push_notification(sender, instance, created, **kwargs):
    if created:
        to_user = instance.content_object.user
        if to_user.registration_id:
            message = None

            if instance.reaction_type == 'bless':
                message = f"{instance.name.username} sent you a blessing."
            elif instance.reaction_type == 'gratitude':
                message = f"{instance.name.username} expressed gratitude."
            elif instance.reaction_type == 'amen':
                message = f"{instance.name.username} said Amen to your post."
            elif instance.reaction_type == 'encouragement':
                message = f"{instance.name.username} sent you encouragement."
            elif instance.reaction_type == 'empathy':
                message = f"{instance.name.username} expressed empathy."

            send_push_notification(
                registration_id=to_user.registration_id,
                message_title="New Reaction",
                message_body=message
            )

# Real-time Notification for new reaction
@receiver(post_save, sender=Reaction)
def send_reaction_real_time_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        to_user = instance.content_object.user

        message = None
        if instance.reaction_type == 'bless':
            message = f"{instance.name.username} sent you a blessing."
        elif instance.reaction_type == 'gratitude':
            message = f"{instance.name.username} expressed gratitude."
        elif instance.reaction_type == 'amen':
            message = f"{instance.name.username} said Amen to your post."
        elif instance.reaction_type == 'encouragement':
            message = f"{instance.name.username} sent you encouragement."
        elif instance.reaction_type == 'empathy':
            message = f"{instance.name.username} expressed empathy."

        async_to_sync(channel_layer.group_send)(
            f"user_{to_user.id}",
            {
                "type": "send_notification",
                "message": message,
            }
        )
        logger.info(f"Real-time notification sent to user {to_user.id}: {message}")