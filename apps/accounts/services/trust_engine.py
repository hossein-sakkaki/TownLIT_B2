# apps/accounts/services/trust_engine.py

from apps.accounts.tasks.trust_tasks import recalculate_trust_score_task


def trigger_trust_recalculation(user_id: int):
    """
    Send trust recalculation to Celery.
    """
    recalculate_trust_score_task.delay(user_id)