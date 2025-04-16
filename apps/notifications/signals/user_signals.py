from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.urls import reverse
from apps.notifications.models import UserNotificationPreference, NOTIFICATION_TYPES
from utils import send_push_notification
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# Standard Notification for creating user notification preferences
@receiver(post_save, sender=CustomUser)
def create_user_notification_preferences(sender, instance, created, **kwargs):
    """
    Automatically create notification preferences for every new user
    to ensure they can manage their notification settings from the control center.
    """
    if created:
        # Create a preference for each notification type
        for notification_type, _ in NOTIFICATION_TYPES:
            UserNotificationPreference.objects.create(user=instance, notification_type=notification_type)

# Push Notification for new user account creation
@receiver(post_save, sender=CustomUser)
def send_welcome_push_notification(sender, instance, created, **kwargs):
    """
    Send a push notification to the user when their account is created,
    informing them that their notification preferences have been set up.
    """
    if created and instance.registration_id:
        send_push_notification(
            registration_id=instance.registration_id,
            message_title="Welcome to TownLIT!",
            message_body="Your notification preferences have been set up. You can manage them in your account settings."
        )

# Real-time Notification for new user account creation
@receiver(post_save, sender=CustomUser)
def send_welcome_real_time_notification(sender, instance, created, **kwargs):
    """
    Send a real-time notification to the user when their account is created,
    informing them that their notification preferences have been set up.
    """
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.id}",
            {
                "type": "send_notification",
                "message": "Your notification preferences have been set up. Manage them in your account settings.",
            }
        )