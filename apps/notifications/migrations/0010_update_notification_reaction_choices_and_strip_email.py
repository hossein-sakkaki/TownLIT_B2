# Generated manually for TownLIT notification email policy update.

from django.db import migrations, models


CHANNEL_EMAIL = 4

NOTIFICATION_TYPE_CHOICES = [
    # --- Content Interactions ---
    ("new_comment", "New Comment"),
    ("new_reply", "New Reply"),
    ("new_reply_post_owner", "Reply to Post Comment"),

    # --- Reactions ---
    ("new_reaction", "New Reaction"),
    ("new_reaction_like", "Like Reaction"),
    ("new_reaction_bless", "Bless Reaction"),
    ("new_reaction_gratitude", "Gratitude Reaction"),
    ("new_reaction_amen", "Amen Reaction"),
    ("new_reaction_encouragement", "Encouragement Reaction"),
    ("new_reaction_empathy", "Empathy Reaction"),
    ("new_reaction_faithfire", "FaithFire Reaction"),
    ("new_reaction_support", "Support Reaction"),

    # --- Friendships ---
    ("friend_request_received", "Friend Request Received"),
    ("friend_request_accepted", "Friend Request Accepted"),
    ("friend_request_declined", "Friend Request Declined"),
    ("friend_request_cancelled", "Friend Request Cancelled"),
    ("friendship_deleted", "Friendship Deleted"),

    # --- Fellowships ---
    ("fellowship_request_received", "Fellowship Request Received"),
    ("fellowship_request_accepted", "Fellowship Request Accepted"),
    ("fellowship_request_confirmed", "Fellowship Relationship Confirmed"),
    ("fellowship_request_declined", "Fellowship Request Declined"),
    ("fellowship_decline_notice", "Fellowship Decline Notice"),
    ("fellowship_cancelled", "Fellowship Cancelled"),

    # --- Messages ---
    ("new_message_direct", "New Direct Message"),
    ("new_message_group", "New Group Message"),

    # --- Testimonies ---
    ("new_testimony_written", "New Written Testimony"),
    ("new_testimony_audio", "New Audio Testimony"),
    ("new_testimony_video", "New Video Testimony"),
    ("testimony_video_rejected", "Video Testimony Not Accepted"),

    # --- Sanctuary ---
    ("sanctuary_admin_assignment", "Sanctuary: Admin Assignment"),
    ("sanctuary_member_review_request", "Sanctuary: Council Review Request"),
    ("sanctuary_outcome_finalized", "Sanctuary: Outcome Finalized"),
    ("sanctuary_appeal_assignment", "Sanctuary: Appeal Assignment"),

    # --- Moments ---
    ("new_moment_image", "New Image Moment"),
    ("new_moment_video", "New Video Moment"),

    # --- Prayers ---
    ("new_prayer_image", "New Image Prayer"),
    ("new_prayer_video", "New Video Prayer"),
    ("prayer_result_answered", "Prayer Answered Update"),
    ("prayer_result_not_answered", "Prayer Update (Not Answered)"),
]


NO_EMAIL_NOTIFICATION_TYPES = {
    # Messenger.
    "new_message_direct",
    "new_message_group",

    # Comments and replies.
    "new_comment",
    "new_reply",
    "new_reply_post_owner",

    # Reactions.
    "new_reaction",
    "new_reaction_like",
    "new_reaction_bless",
    "new_reaction_gratitude",
    "new_reaction_amen",
    "new_reaction_encouragement",
    "new_reaction_empathy",
    "new_reaction_faithfire",
    "new_reaction_support",

    # Standard friendships.
    "friend_request_received",
    "friend_request_accepted",
    "friend_request_declined",
    "friend_request_cancelled",
    "friendship_deleted",

    # Feed content from friends/circle.
    "new_moment_image",
    "new_moment_video",
    "new_prayer_image",
    "new_prayer_video",
    "prayer_result_answered",
    "prayer_result_not_answered",
    "new_testimony_written",
    "new_testimony_audio",
    "new_testimony_video",
}


def strip_email_channel_from_high_frequency_notifications(apps, schema_editor):
    UserNotificationPreference = apps.get_model(
        "notifications",
        "UserNotificationPreference",
    )

    prefs = UserNotificationPreference.objects.filter(
        notification_type__in=NO_EMAIL_NOTIFICATION_TYPES,
    )

    for pref in prefs.iterator():
        old_mask = int(pref.channels_mask or 0)
        new_mask = old_mask & ~CHANNEL_EMAIL

        if new_mask != old_mask:
            pref.channels_mask = new_mask
            pref.save(update_fields=["channels_mask"])


def noop_reverse(apps, schema_editor):
    # Do not restore email for high-frequency notification types on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0009_alter_notification_notification_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=NOTIFICATION_TYPE_CHOICES,
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="usernotificationpreference",
            name="notification_type",
            field=models.CharField(
                choices=NOTIFICATION_TYPE_CHOICES,
                max_length=50,
            ),
        ),
        migrations.RunPython(
            strip_email_channel_from_high_frequency_notifications,
            noop_reverse,
        ),
    ]