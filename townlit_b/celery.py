# townlit_b/celery.py

from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "townlit_b.settings")

app = Celery("townlit_b")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Define all beat schedules in one dictionary ------------------------------------------
app.conf.beat_schedule = {

    # Delete inactive users daily
    "delete-inactive-users-every-day": {
        "task": "apps.profiles.tasks.delete_inactive_entities",
        "schedule": crontab(hour=0, minute=0),
    },

    # Delete inactive organizations daily
    "delete-inactive-organizations-every-day": {
        "task": "apps.profilesOrg.tasks.delete_inactive_entities",
        "schedule": crontab(hour=0, minute=0),
    },

    # Notify single-owner organizations every 3 months
    "notify-single-owner-organizations": {
        "task": "apps.profilesOrg.tasks.notify_single_owner_organizations",
        "schedule": crontab(hour=0, minute=0, day_of_month="1", month_of_year="*/3"),
    },

    # Sanctuary reviewer fallback every 48 hours
    "check-for-inactive-reviewers-every-48-hours": {
        "task": "apps.sanctuary.tasks.check_for_inactive_reviewers",
        "schedule": crontab(minute=0, hour="*/48"),
    },

    # Sanctuary admin fallback every 24 hours
    "check-for-inactive-admins-every-24-hours": {
        "task": "apps.sanctuary.tasks.check_for_inactive_admins",
        "schedule": crontab(minute=0, hour="*/24"),
    },

    # Sanctuary appeal admin fallback every 24 hours
    "check-for-inactive-appeal-admins-every-24-hours": {
        "task": "apps.sanctuary.tasks.check_for_inactive_appeal_admins",
        "schedule": crontab(minute=0, hour="*/24"),
    },

    # Check appeal deadlines daily
    "check-appeal-deadlines-daily": {
        "task": "apps.sanctuary.tasks.check_appeal_deadlines",
        "schedule": crontab(hour=0, minute=0),
    },

    # Delete expired tokens every 2 hours
    "delete-expired-tokens-every-2-hours": {
        "task": "apps.accounts.tasks.maintenance_tasks.delete_expired_tokens",
        "schedule": crontab(hour="*/2"),
    },

    # Retry undelivered private messages every 5 minutes
    "retry-undelivered-messages-every-5-minutes": {
        "task": "apps.conversation.tasks.retry_undelivered_messages",
        "schedule": crontab(minute="*/5"),
    },

    # Cleanup expired message pins every 5 minutes
    "cleanup-expired-message-pins-every-5-minutes": {
        "task": "apps.conversation.tasks.cleanup_expired_message_pins",
        "schedule": crontab(minute="*/5"),
    },

    # Send due message pin reminders every 5 minutes
    "send-due-message-pin-reminders-every-5-minutes": {
        "task": "apps.conversation.tasks.send_due_message_pin_reminders",
        "schedule": crontab(minute="*/5"),
    },

    # Expire old pending payments every 6 hours
    "expire-old-pending-payments-every-6-hours": {
        "task": "apps.payment.tasks.expire_old_pending_payments",
        "schedule": crontab(minute=0, hour="*/6"),
    },

    # Run scheduled emails every 2 minutes
    "run-scheduled-emails-every-2-minutes": {
        "task": "apps.communication.tasks.run_scheduled_emails",
        "schedule": crontab(minute="*/2"),
    },

    # Delete abandoned users daily
    "delete-abandoned-users-daily": {
        "task": "apps.accounts.tasks.maintenance_tasks.delete_abandoned_users",
        "schedule": crontab(hour=3, minute=0),
    },

    # Sanctuary reviewer fallback every 2 hours
    "check-for-inactive-reviewers-every-2-hours": {
        "task": "apps.sanctuary.tasks.check_for_inactive_reviewers",
        "schedule": crontab(minute=0, hour="*/2"),
    },

    # Sanctuary admin fallback every 2 hours
    "check-for-inactive-admins-every-2-hours": {
        "task": "apps.sanctuary.tasks.check_for_inactive_admins",
        "schedule": crontab(minute=0, hour="*/2"),
    },

    # Sanctuary appeal admin fallback every 2 hours
    "check-for-inactive-appeal-admins-every-2-hours": {
        "task": "apps.sanctuary.tasks.check_for_inactive_appeal_admins",
        "schedule": crontab(minute=0, hour="*/2"),
    },

    # Auto-fail stale media conversion jobs every minute
    "auto-fail-stale-media-jobs-every-minute": {
        "task": "apps.media_conversion.tasks.health.auto_fail_stale_media_jobs",
        "schedule": crontab(minute="*/1"),
    },
}



# celery -A townlit_b worker -l info
# celery -A townlit_b beat -l info