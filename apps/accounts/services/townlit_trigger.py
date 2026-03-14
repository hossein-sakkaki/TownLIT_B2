# apps/accounts/services/townlit_trigger.py

from apps.accounts.tasks.townlit_tasks import evaluate_member_townlit_badge_task


def trigger_member_townlit_evaluation(member_id: int):
    evaluate_member_townlit_badge_task.delay(member_id)