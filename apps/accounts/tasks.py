from celery import shared_task
from django.utils import timezone
from .models import CustomUser

@shared_task
def delete_expired_tokens():
    CustomUser.objects.filter(reset_token_expiration__lt=timezone.now()).update(reset_token=None, reset_token_expiration=None)
