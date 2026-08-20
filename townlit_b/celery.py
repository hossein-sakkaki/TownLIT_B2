# townlit_b/celery.py

from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "townlit_b.settings",
)

app = Celery("townlit_b")

app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)

app.autodiscover_tasks()


# Route domain-specific tasks to dedicated queues.
app.conf.task_routes = {
    "apps.creative_editor.tasks.render.render_creative_composition_task": {
        "queue": "creative_render",
    },
}


# Define all beat schedules in one dictionary.
app.conf.beat_schedule = {

    # Permanently purge expired account deletions hourly.
    "purge-scheduled-account-deletions-hourly": {
        "task": (
            "apps.accounts.tasks."
            "maintenance_tasks."
            "purge_scheduled_account_deletions"
        ),
        "schedule": crontab(
            minute=20,
            hour="*",
        ),
    },

    # Delete inactive organizations daily.
    "delete-inactive-organizations-every-day": {
        "task": "apps.profilesOrg.tasks.delete_inactive_entities",
        "schedule": crontab(
            hour=0,
            minute=0,
        ),
    },

    # Notify single-owner organizations every 3 months.
    "notify-single-owner-organizations": {
        "task": (
            "apps.profilesOrg.tasks."
            "notify_single_owner_organizations"
        ),
        "schedule": crontab(
            hour=0,
            minute=0,
            day_of_month="1",
            month_of_year="*/3",
        ),
    },

    # Check appeal deadlines daily.
    "check-appeal-deadlines-daily": {
        "task": (
            "apps.sanctuary.tasks."
            "check_appeal_deadlines"
        ),
        "schedule": crontab(
            hour=0,
            minute=0,
        ),
    },

    # Delete expired tokens every 2 hours.
    "delete-expired-tokens-every-2-hours": {
        "task": (
            "apps.accounts.tasks."
            "maintenance_tasks.delete_expired_tokens"
        ),
        "schedule": crontab(
            hour="*/2",
        ),
    },

    # Retry undelivered private messages every 5 minutes.
    "retry-undelivered-messages-every-5-minutes": {
        "task": (
            "apps.conversation.tasks."
            "retry_undelivered_messages"
        ),
        "schedule": crontab(
            minute="*/5",
        ),
    },

    # Cleanup expired message pins every 5 minutes.
    "cleanup-expired-message-pins-every-5-minutes": {
        "task": (
            "apps.conversation.tasks."
            "cleanup_expired_message_pins"
        ),
        "schedule": crontab(
            minute="*/5",
        ),
    },

    # Send due message pin reminders every 5 minutes.
    "send-due-message-pin-reminders-every-5-minutes": {
        "task": (
            "apps.conversation.tasks."
            "send_due_message_pin_reminders"
        ),
        "schedule": crontab(
            minute="*/5",
        ),
    },

    # Expire old pending payments every 6 hours.
    "expire-old-pending-payments-every-6-hours": {
        "task": (
            "apps.payment.tasks."
            "expire_old_pending_payments"
        ),
        "schedule": crontab(
            minute=0,
            hour="*/6",
        ),
    },

    # Dispatch due communication campaigns every minute.
    "dispatch-due-email-campaigns-every-minute": {
        "task": (
            "apps.communication.tasks."
            "dispatch_due_campaigns"
        ),
        "schedule": crontab(
            minute="*",
        ),
    },

    # Recover communication campaigns stuck in queue.
    "recover-stale-email-campaigns-every-5-minutes": {
        "task": (
            "apps.communication.tasks."
            "recover_stale_campaigns"
        ),
        "schedule": crontab(
            minute="*/5",
        ),
    },

    # Delete abandoned users daily.
    "delete-abandoned-users-daily": {
        "task": (
            "apps.accounts.tasks."
            "maintenance_tasks.delete_abandoned_users"
        ),
        "schedule": crontab(
            hour=3,
            minute=0,
        ),
    },

    # Sanctuary reviewer fallback every 2 hours.
    "check-for-inactive-reviewers-every-2-hours": {
        "task": (
            "apps.sanctuary.tasks."
            "check_for_inactive_reviewers"
        ),
        "schedule": crontab(
            minute=0,
            hour="*/2",
        ),
    },

    # Sanctuary admin fallback every 2 hours.
    "check-for-inactive-admins-every-2-hours": {
        "task": (
            "apps.sanctuary.tasks."
            "check_for_inactive_admins"
        ),
        "schedule": crontab(
            minute=0,
            hour="*/2",
        ),
    },

    # Sanctuary appeal admin fallback every 2 hours.
    "check-for-inactive-appeal-admins-every-2-hours": {
        "task": (
            "apps.sanctuary.tasks."
            "check_for_inactive_appeal_admins"
        ),
        "schedule": crontab(
            minute=0,
            hour="*/2",
        ),
    },

    # Auto-fail stale media conversion jobs every minute.
    "auto-fail-stale-media-jobs-every-minute": {
        "task": (
            "apps.media_conversion.tasks.health."
            "auto_fail_stale_media_jobs"
        ),
        "schedule": crontab(
            minute="*/1",
        ),
    },

    # Rebuild audio trending scores every 15 minutes.
    "rebuild-audio-trending-scores-every-15-minutes": {
        "task": (
            "apps.audio_catalog.analytics.tasks."
            "rebuild_audio_trending_scores"
        ),
        "schedule": crontab(
            minute="*/15",
        ),
    },

    # Close stale audio playback sessions every 10 minutes.
    "close-stale-audio-playback-sessions-every-10-minutes": {
        "task": (
            "apps.audio_catalog.analytics.tasks."
            "close_stale_audio_playback_sessions"
        ),
        "schedule": crontab(
            minute="*/10",
        ),
    },

    # Purge old raw audio playback sessions every day.
    "purge-old-audio-playback-sessions-daily": {
        "task": (
            "apps.audio_catalog.analytics.tasks."
            "purge_old_audio_playback_sessions"
        ),
        "schedule": crontab(
            hour=4,
            minute=10,
        ),
    },

    # Purge old unique-listener guards every day.
    "purge-old-audio-listener-rows-daily": {
        "task": (
            "apps.audio_catalog.analytics.tasks."
            "purge_old_audio_unique_listener_rows"
        ),
        "schedule": crontab(
            hour=4,
            minute=20,
        ),
    },
    
    # Recover stale Creative Editor renders every 5 minutes.
    "recover-stale-creative-renders-every-5-minutes": {
        "task": (
            "apps.creative_editor.tasks.health."
            "recover_stale_creative_render_jobs"
        ),
        "schedule": crontab(
            minute="*/5",
        ),
    },
    
    # Process expired Journey entries every 5 minutes.
    "process-expired-journey-entries": {
        "task": (
            "apps.posts.tasks.journeys."
            "process_expired_journey_entries"
        ),
        "schedule": crontab(
            minute="*/5",
        ),
    },
    
    # Send the daily bookstore inventory summary.
    "send-daily-bookstore-inventory-summary": {
        "task": (
            "apps.bookstore_inventory.tasks."
            "send_daily_inventory_report"
        ),
        "schedule": crontab(
            hour=14,  # 07:00 Vancouver while UTC-7
            minute=0,
        ),
        "options": {
            "expires": 2 * 60 * 60,
        },
    },
}


# celery -A townlit_b worker -l info
# celery -A townlit_b beat -l info