from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.notifications.models import Notification
from apps.posts.models import Moment, Testimony, Pray, Announcement, Lesson, Preach, Worship, Witness, Library
from utils import send_push_notification

# Standard Notification for new post-related content
@receiver(post_save, sender=Moment)
@receiver(post_save, sender=Testimony)
@receiver(post_save, sender=Pray)
@receiver(post_save, sender=Announcement)
@receiver(post_save, sender=Lesson)
@receiver(post_save, sender=Preach)
@receiver(post_save, sender=Worship)
@receiver(post_save, sender=Witness)
@receiver(post_save, sender=Library)
def create_post_notification(sender, instance, created, **kwargs):
    if created:
        notification_type = None
        message = None
        link = None

        if isinstance(instance, Moment):
            notification_type = 'new_moment'
            message = f"New Moment Created: {instance.content[:30]}..."
            link = reverse('Moment_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Testimony):
            notification_type = 'new_testimony'
            message = f"New Testimony: {instance.title}"
            link = reverse('Testimony_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Pray):
            notification_type = 'new_pray'
            message = f"New Pray: {instance.title}"
            link = reverse('Pray_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Announcement):
            notification_type = 'new_announcement'
            message = f"New Announcement: {instance.title}"
            link = reverse('Announcement_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Lesson):
            notification_type = 'new_lesson'
            message = f"New Lesson: {instance.title}"
            link = reverse('Lesson_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Preach):
            notification_type = 'new_preach'
            message = f"New Preach: {instance.title}"
            link = reverse('Preach_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Worship):
            notification_type = 'new_worship'
            message = f"New Worship: {instance.title}"
            link = reverse('Worship_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Witness):
            notification_type = 'new_witness'
            message = f"New Witness: {instance.title}"
            link = reverse('Witness_detail', kwargs={'pk': instance.pk})
        elif isinstance(instance, Library):
            notification_type = 'new_library_item'
            message = f"New Library Item: {instance.book_name}"
            link = reverse('Library_detail', kwargs={'pk': instance.pk})

        if notification_type:
            Notification.objects.create(
                user=instance.user,
                message=message,
                notification_type=notification_type,
                content_type=ContentType.objects.get_for_model(sender),
                object_id=instance.id,
                link=link
            )

# Push Notification for new post-related content
@receiver(post_save, sender=Moment)
@receiver(post_save, sender=Testimony)
@receiver(post_save, sender=Pray)
@receiver(post_save, sender=Announcement)
@receiver(post_save, sender=Lesson)
@receiver(post_save, sender=Preach)
@receiver(post_save, sender=Worship)
@receiver(post_save, sender=Witness)
@receiver(post_save, sender=Library)
def send_post_push_notification(sender, instance, created, **kwargs):
    if created:
        to_user = instance.user
        if to_user.registration_id:
            message = f"New Content Added: {instance.title}" if hasattr(instance, 'title') else f"New Post: {instance.content[:30]}..."
            send_push_notification(
                registration_id=to_user.registration_id,
                message_title="New Content",
                message_body=message
            )

# Real-time Notification for new post-related content
@receiver(post_save, sender=Moment)
@receiver(post_save, sender=Testimony)
@receiver(post_save, sender=Pray)
@receiver(post_save, sender=Announcement)
@receiver(post_save, sender=Lesson)
@receiver(post_save, sender=Preach)
@receiver(post_save, sender=Worship)
@receiver(post_save, sender=Witness)
@receiver(post_save, sender=Library)
def send_post_real_time_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.user.id}",
            {
                "type": "send_notification",
                "message": f"New Content Added: {instance.title}" if hasattr(instance, 'title') else f"New Post: {instance.content[:30]}...",
            }
        )
