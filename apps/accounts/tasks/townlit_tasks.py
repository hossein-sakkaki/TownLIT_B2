# apps/accounts/tasks/townlit_tasks.py

from celery import shared_task

from apps.profiles.models import Member
from apps.accounts.services.townlit_engine import evaluate_and_apply_member_townlit_badge


@shared_task
def evaluate_member_townlit_badge_task(member_id: int):
    try:
        member = Member.objects.get(pk=member_id)
    except Member.DoesNotExist:
        return

    evaluate_and_apply_member_townlit_badge(member)