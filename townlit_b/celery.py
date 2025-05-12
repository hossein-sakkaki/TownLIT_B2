from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'townlit_b.settings')
app = Celery('townlit_b')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()



# Define all beat schedules in one dictionary
app.conf.beat_schedule = {
    # ✅ Cancel Friendship After 3 Months
    # 'delete_expired_friendships_every_day': {
    #     'task': 'apps.profiles.tasks.delete_expired_friendships',
    #     'schedule': crontab(hour=0, minute=0),
    # },

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


}



# celery -A townlit_b worker -l info
# celery -A townlit_b beat -l info