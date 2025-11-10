from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


from apps.conversation.models import Message, Dialogue
from apps.notifications.models import Notification
from utils.common.push_notification import send_push_notification

from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# STANDARD NOTIFICATION for Create Message -----------------------------------------------------------------
@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    if created:
        # Notify all participants except the sender
        dialogue = instance.dialogue
        participants = dialogue.participants.exclude(id=instance.sender.id)
        for user in participants:
            Notification.objects.create(
                user=user,
                message=f"New message from {instance.sender.username} in {dialogue.name or 'a conversation'}.",
                notification_type='message_received',
                content_type=ContentType.objects.get_for_model(sender),
                object_id=instance.id,
                link=reverse('message_detail', kwargs={'pk': instance.pk})  # Adjust the link as needed
            )


# PUSH NOTIFICATION for Send Message -----------------------------------------------------------------------
@receiver(post_save, sender=Message)
def send_message_push_notification(sender, instance, created, **kwargs):
    if created:
        dialogue = instance.dialogue
        participants = dialogue.participants.exclude(id=instance.sender.id)
        for user in participants:
            if user.registration_id:
                message = f"New message from {instance.sender.username} in {dialogue.name or 'a conversation'}."
                send_push_notification(
                    registration_id=user.registration_id,
                    message_title="New Message",
                    message_body=message
                )


# REAL-TIME NOTIFICATION for Send Message -------------------------------------------------------------------
@receiver(post_save, sender=Message)
def send_message_real_time_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        dialogue = instance.dialogue
        participants = dialogue.participants.exclude(id=instance.sender.id)

        for user in participants:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "send_notification",
                    "message": f"New message from {instance.sender.username} in {dialogue.name or 'a conversation'}.",
                }
            )


# STANDARD NOTIFICATION for Add Participant -----------------------------------------------------------------
@receiver(m2m_changed, sender=Dialogue.participants.through)
def notify_participant_added(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add' and instance.is_group:
        new_participants = CustomUser.objects.filter(pk__in=pk_set)
        for new_participant in new_participants:
            for user in instance.participants.exclude(id=new_participant.id):
                Notification.objects.create(
                    user=user,
                    message=f"{new_participant.username} has joined the group {instance.name}.",
                    notification_type='group_event',
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    link=reverse('group_detail', kwargs={'pk': instance.pk})
                )
               
                
# STANDARD NOTIFICATION for Remove Participant --------------------------------------------------------------
@receiver(m2m_changed, sender=Dialogue.participants.through)
def notify_participant_removed(sender, instance, action, pk_set, **kwargs):
    if action == 'post_remove' and instance.is_group:
        removed_participants = CustomUser.objects.filter(pk__in=pk_set)
        for removed_participant in removed_participants:
            for user in instance.participants.exclude(id=removed_participant.id):
                Notification.objects.create(
                    user=user,
                    message=f"{removed_participant.username} has left the group {instance.name}.",
                    notification_type='group_event',
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    link=reverse('group_detail', kwargs={'pk': instance.pk})
                )
                

# STANDARD NOTIFICATION for Admin Group Change --------------------------------------------------------------
@receiver(post_save, sender=Dialogue)
def notify_group_admin_change(sender, instance, created, **kwargs):
    if not created and instance.is_group:
        new_admin = instance.admin
        for user in instance.participants.exclude(id=new_admin.id):
            Notification.objects.create(
                user=user,
                message=f"{new_admin.username} is now the admin of the group {instance.name}.",
                notification_type='group_event',
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.id,
                link=reverse('group_detail', kwargs={'pk': instance.pk})
            )


# PUSH NOTIFICATION for Add or Remove Post -------------------------------------------------------------------
@receiver(m2m_changed, sender=Dialogue.participants.through)
def send_group_push_notification(sender, instance, action, pk_set, **kwargs):
    if action in ['post_add', 'post_remove'] and instance.is_group:
        participants = instance.participants.all()
        event = "joined" if action == 'post_add' else "left"
        new_participants = CustomUser.objects.filter(pk__in=pk_set)
        for user in participants:
            for participant in new_participants:
                if user.registration_id:
                    message = f"{participant.username} has {event} the group {instance.name}."
                    send_push_notification(
                        registration_id=user.registration_id,
                        message_title="Group Event",
                        message_body=message
                    )


# REAL-TIME NOTIFICATION for Add or Remove Post --------------------------------------------------------------
@receiver(m2m_changed, sender=Dialogue.participants.through)
def send_group_real_time_notification(sender, instance, action, pk_set, **kwargs):
    if action in ['post_add', 'post_remove'] and instance.is_group:
        channel_layer = get_channel_layer()
        participants = instance.participants.all()
        event = "joined" if action == 'post_add' else "left"
        new_participants = CustomUser.objects.filter(pk__in=pk_set)
        for user in participants:
            for participant in new_participants:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {
                        "type": "send_notification",
                        "message": f"{participant.username} has {event} the group {instance.name}.",
                    }
                )
