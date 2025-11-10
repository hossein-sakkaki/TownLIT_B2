# apps/notifications/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

# Async Email Notification -------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_email_notification(self, email, subject, message, link=None):
    """Send notification email via Celery"""
    try:
        body = f"{message}\n\nView: {link or 'Open TownLIT app'}"
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:
        raise self.retry(exc=e, countdown=10)
