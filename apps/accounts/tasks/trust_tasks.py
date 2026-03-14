# apps/accounts/tasks/trust_tasks.py

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.accounts.services.trust_score import update_user_trust_score

User = get_user_model()


@shared_task
def recalculate_trust_score_task(user_id):
    """
    Recalculate trust score in background.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    update_user_trust_score(user)