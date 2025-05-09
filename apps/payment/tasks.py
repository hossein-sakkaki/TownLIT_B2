from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .models import Payment

@shared_task
def expire_old_pending_payments():
    threshold = timezone.now() - timedelta(hours=6)  # ⏰ زمان انقضا قابل تنظیم
    expired_count = (
        Payment.objects
        .filter(payment_status='pending', created_at__lt=threshold)
        .update(payment_status='expired')
    )
    return f"{expired_count} pending payments expired."
