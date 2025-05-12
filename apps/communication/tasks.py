# apps/communication/tasks.py

from celery import shared_task
from django.utils.timezone import now
from .models import ScheduledEmail
from .services import send_campaign_email_batch


    

@shared_task
def run_scheduled_emails():
    scheduled_list = ScheduledEmail.objects.filter(is_sent=False, run_at__lte=now())
    count = 0
    for scheduled in scheduled_list:
        try:
            send_campaign_email_batch(scheduled.campaign.id)
            scheduled.is_sent = True
            scheduled.executed_at = now()
            scheduled.save()
            count += 1
        except Exception as e:
            print(f"❌ Failed to send scheduled campaign {scheduled.id}: {e}")
    print(f"✅ {count} scheduled campaign(s) sent.")
