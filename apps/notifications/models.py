from django.db import models
from django.utils import timezone 
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# Notification Types ---------------------------------------------------------------------------------
NOTIFICATION_TYPES = [
    ('new_comment', 'New Comment Added'),
    ('new_recomment', 'New Recomment Added'),
    
    ('new_post', 'New Post Created'),
    ('new_testimony', 'New Testimony Created'),
    ('new_pray', 'New Pray Created'),
    ('new_announcement', 'New Announcement Created'),
    ('new_lesson', 'New Lesson Created'),
    ('new_preach', 'New Preach Created'),
    ('new_worship', 'New Worship Created'),
    ('new_witness', 'New Witness Created'),
    ('new_library_item', 'New Library Item Added'),
    
    ('new_bless', 'New Bless Received'),
    ('new_gratitude', 'New Gratitude Received'),
    ('new_amen', 'New Amen Received'),
    ('new_encouragement', 'New Encouragement Received'),
    ('new_empathy', 'New Empathy Received'),

    ('friend_request_received', 'Friend Request Received'),
    ('friend_request_accepted', 'Friend Request Accepted'),
    ('friend_request_declined', 'Friend Request Declined'),
    
    ('manager_appointed', 'Manager Appointed'),
    ('user_notification_preferences_created', 'User Notification Preferences Created'),

    ('sanctuary_request', 'Sanctuary Request Submitted'),
    ('sanctuary_admin_assignment', 'Sanctuary Admin Assignment'), # مطمئن نیستم چی هست
    ('organization_management', 'Organization Management'),

    # Notifications for Messages and Groups
    ('message_received', 'New Message Received'),
    ('group_event', 'Group Event Notification'),
    ('participant_added', 'Participant Added to Group'),
    ('participant_removed', 'Participant Removed from Group'),
    ('admin_changed', 'Group Admin Changed'),

    ('trusted_friend_alert', 'Trusted Friend Alert'),
    ('product_unavailable', 'Product Unavailable'),

    
]
    
# User Notification Preference models ---------------------------------------------------------------------
class UserNotificationPreference(models.Model):
    user = models.ForeignKey(CustomUser, related_name='notification_preferences', on_delete=models.CASCADE, verbose_name="User")
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, verbose_name="Notification Type")
    enabled = models.BooleanField(default=True, verbose_name="Is Enabled")
    
    class Meta:
        unique_together = ('user', 'notification_type')
        verbose_name = 'User Notification Preference'
        verbose_name_plural = 'User Notification Preferences'

    def __str__(self):
        return f"{self.user.username} - {self.get_notification_type_display()} - {'Enabled' if self.enabled else 'Disabled'}"
    
# Notification models ------------------------------------------------------------------------------------
class Notification(models.Model):
    user = models.ForeignKey(CustomUser, related_name='notifications', on_delete=models.CASCADE, verbose_name="User")
    message = models.TextField(verbose_name="Message")
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, verbose_name="Notification Type")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created At")
    is_read = models.BooleanField(default=False, verbose_name="Is Read")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Content Type")
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="Object ID")
    content_object = GenericForeignKey('content_type', 'object_id')
    link = models.URLField(null=True, blank=True, verbose_name="Link")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"Notification for {self.user} - {self.message}"
    

class NotificationLog(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification Log for {self.recipient.username} - {self.notification.message}"