# Generated by Django 4.2.4 on 2025-03-25 02:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField(verbose_name='Message')),
                ('notification_type', models.CharField(choices=[('new_comment', 'New Comment Added'), ('new_recomment', 'New Recomment Added'), ('new_post', 'New Post Created'), ('new_testimony', 'New Testimony Created'), ('new_pray', 'New Pray Created'), ('new_announcement', 'New Announcement Created'), ('new_lesson', 'New Lesson Created'), ('new_preach', 'New Preach Created'), ('new_worship', 'New Worship Created'), ('new_witness', 'New Witness Created'), ('new_library_item', 'New Library Item Added'), ('new_bless', 'New Bless Received'), ('new_gratitude', 'New Gratitude Received'), ('new_amen', 'New Amen Received'), ('new_encouragement', 'New Encouragement Received'), ('new_empathy', 'New Empathy Received'), ('friend_request_received', 'Friend Request Received'), ('friend_request_accepted', 'Friend Request Accepted'), ('friend_request_declined', 'Friend Request Declined'), ('manager_appointed', 'Manager Appointed'), ('user_notification_preferences_created', 'User Notification Preferences Created'), ('sanctuary_request', 'Sanctuary Request Submitted'), ('sanctuary_admin_assignment', 'Sanctuary Admin Assignment'), ('organization_management', 'Organization Management'), ('message_received', 'New Message Received'), ('group_event', 'Group Event Notification'), ('participant_added', 'Participant Added to Group'), ('participant_removed', 'Participant Removed from Group'), ('admin_changed', 'Group Admin Changed'), ('trusted_friend_alert', 'Trusted Friend Alert'), ('product_unavailable', 'Product Unavailable')], max_length=50, verbose_name='Notification Type')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Created At')),
                ('is_read', models.BooleanField(default=False, verbose_name='Is Read')),
                ('object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Object ID')),
                ('link', models.URLField(blank=True, null=True, verbose_name='Link')),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='Content Type')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Notification',
                'verbose_name_plural': 'Notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='notifications.notification')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserNotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('new_comment', 'New Comment Added'), ('new_recomment', 'New Recomment Added'), ('new_post', 'New Post Created'), ('new_testimony', 'New Testimony Created'), ('new_pray', 'New Pray Created'), ('new_announcement', 'New Announcement Created'), ('new_lesson', 'New Lesson Created'), ('new_preach', 'New Preach Created'), ('new_worship', 'New Worship Created'), ('new_witness', 'New Witness Created'), ('new_library_item', 'New Library Item Added'), ('new_bless', 'New Bless Received'), ('new_gratitude', 'New Gratitude Received'), ('new_amen', 'New Amen Received'), ('new_encouragement', 'New Encouragement Received'), ('new_empathy', 'New Empathy Received'), ('friend_request_received', 'Friend Request Received'), ('friend_request_accepted', 'Friend Request Accepted'), ('friend_request_declined', 'Friend Request Declined'), ('manager_appointed', 'Manager Appointed'), ('user_notification_preferences_created', 'User Notification Preferences Created'), ('sanctuary_request', 'Sanctuary Request Submitted'), ('sanctuary_admin_assignment', 'Sanctuary Admin Assignment'), ('organization_management', 'Organization Management'), ('message_received', 'New Message Received'), ('group_event', 'Group Event Notification'), ('participant_added', 'Participant Added to Group'), ('participant_removed', 'Participant Removed from Group'), ('admin_changed', 'Group Admin Changed'), ('trusted_friend_alert', 'Trusted Friend Alert'), ('product_unavailable', 'Product Unavailable')], max_length=50, verbose_name='Notification Type')),
                ('enabled', models.BooleanField(default=True, verbose_name='Is Enabled')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'User Notification Preference',
                'verbose_name_plural': 'User Notification Preferences',
                'unique_together': {('user', 'notification_type')},
            },
        ),
    ]
