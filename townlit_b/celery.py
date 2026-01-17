# townlit_b/celery.py
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'townlit_b.settings')
app = Celery('townlit_b')
app.config_from_object('django.conf:settings', namespace='CELERY') 
app.autodiscover_tasks()


# Define all beat schedules in one dictionary ------------------------------------------
app.conf.beat_schedule = {

    # ✅ Delete Inactive Users
    'delete-inactive-users-every-day': {
        'task': 'apps.profiles.tasks.delete_inactive_entities',
        'schedule': crontab(hour=0, minute=0),
    },

    # ✅ Delete Inactive Organizations
    'delete-inactive-organizations-every-day': {
        'task': 'apps.profilesOrg.tasks.delete_inactive_entities',
        'schedule': crontab(hour=0, minute=0),
    },

    # ✅ Notify Single Owner Organizations (Every 3 Months)
    'notify-single-owner-organizations': {
        'task': 'apps.profilesOrg.tasks.notify_single_owner_organizations',
        'schedule': crontab(hour=0, minute=0, day_of_month='1', month_of_year='*/3'),
    },

    # ✅ Replace Member for Sanctuary (Every 48 hours)
    'check_for_inactive_reviewers_every_48_hours': {
        'task': 'apps.sanctuary.tasks.check_for_inactive_reviewers',
        'schedule': crontab(hour='*/48'),
    },

    # ✅ Reassign Admin for Sanctuary (Every 24 hours)
    'check_for_inactive_admins_every_24_hours': {
        'task': 'apps.sanctuary.tasks.check_for_inactive_admins',
        'schedule': crontab(hour='*/24'),
    },

    # ✅ Replace Admin for Appeal (Every 24 hours)
    'check_for_inactive_appeal_admins_every_24_hours': {
        'task': 'apps.sanctuary.tasks.check_for_inactive_appeal_admins',
        'schedule': crontab(hour='*/24'),
    },

    # ✅ Check Appeal Deadlines (Daily)
    'check-appeal-deadlines-every-day': {
        'task': 'apps.sanctuary.tasks.check_appeal_deadlines',
        'schedule': crontab(hour=0, minute=0),
    },

    # ✅ Delete Expired Tokens (Every 2 hours)
    'delete-expired-tokens-every-2-hours': {
        'task': 'apps.accounts.tasks.delete_expired_tokens',
        'schedule': crontab(hour='*/2'),
    },
    
    # Undelivered Messages
    'retry-undelivered-messages-every-5-minutes': {
        'task': 'apps.conversation.tasks.deliver_offline_message',
        'schedule': crontab(minute='*/5'),
    },

    
    'retry-undelivered-messages-every-5-minutes': {
        'task': 'apps.conversation.tasks.retry_undelivered_messages',
        'schedule': crontab(minute='*/5'),  # هر ۵ دقیقه
    },

    
    # ✅ Expire Old Pending Payments
    'expire-old-pending-payments-every-6-hours': {
        'task': 'apps.payment.tasks.expire_old_pending_payments',
        'schedule': crontab(minute=0, hour='*/6'),  # هر ۶ ساعت
        # 'schedule': crontab(hour=0, minute=0),  # daily at midnight
    },
    
    'run_scheduled_emails_every_2_minutes': {
        'task': 'apps.communication.tasks.run_scheduled_emails',
        'schedule': crontab(minute='*/2'),  # هر ۲ دقیقه
    },
    
    'delete-abandoned-users-daily': {
        'task': 'apps.accounts.tasks.delete_abandoned_users',
        'schedule': crontab(hour=3, minute=0),  # هر روز ساعت ۳ صبح
    },

    # ✅ Replace Member for Sanctuary (run every 2 hours; replaces only after 48h cutoff)
    'check_for_inactive_reviewers_every_2_hours': {
        'task': 'apps.sanctuary.tasks.check_for_inactive_reviewers',
        'schedule': crontab(minute=0, hour='*/2'),
    },

    # ✅ Reassign Admin for Sanctuary (run every 2 hours; cutoff is 24h inside task)
    'check_for_inactive_admins_every_2_hours': {
        'task': 'apps.sanctuary.tasks.check_for_inactive_admins',
        'schedule': crontab(minute=0, hour='*/2'),
    },

    # ✅ Replace Admin for Appeal (run every 2 hours; cutoff is 24h inside task)
    'check_for_inactive_appeal_admins_every_2_hours': {
        'task': 'apps.sanctuary.tasks.check_for_inactive_appeal_admins',
        'schedule': crontab(minute=0, hour='*/2'),
    },

    # ✅ Check Appeal Deadlines (daily midnight is fine)
    'check-appeal-deadlines-every-day': {
        'task': 'apps.sanctuary.tasks.check_appeal_deadlines',
        'schedule': crontab(hour=0, minute=0),
    },

    # 🧠 Auto-fail stale media conversion jobs (every 1 minute)
    'auto-fail-stale-media-jobs-every-minute': {
        'task': 'apps.media_conversion.tasks.health.auto_fail_stale_media_jobs',
        'schedule': crontab(minute='*/1'),
    },

}



# celery -A townlit_b worker -l info
# celery -A townlit_b beat -l info