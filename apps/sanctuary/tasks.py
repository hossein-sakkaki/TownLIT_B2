from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import SanctuaryReview, SanctuaryRequest, SanctuaryOutcome
from apps.sanctuary.signals.signals import distribute_to_verified_members, finalize_sanctuary_outcome
from apps.notifications.models import Notification
from apps.config.sanctuary_constants import PENDING
import logging
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)

#    ----------------------------------------
@shared_task
def check_for_inactive_reviewers():
    deadline = timezone.now() - timedelta(hours=48)
    inactive_reviews = SanctuaryReview.objects.filter(
        review_status='no_opinion',
        created_at__lt=deadline
    )
    for review in inactive_reviews:
        review.delete()
        sanctuary_request = review.sanctuary_request
        distribute_to_verified_members(sanctuary_request)


#    ----------------------------------------
@shared_task
def check_for_inactive_admins():
    threshold_time = timezone.now() - timedelta(hours=24)
    inactive_requests = SanctuaryRequest.objects.filter(admin_assigned_at__lt=threshold_time, status=PENDING)
    for request in inactive_requests:
        admins = CustomUser.objects.filter(is_staff=True).exclude(id=request.assigned_admin.id)
        if admins.exists():
            new_admin = admins.order_by('?').first()
            request.assigned_admin = new_admin
            request.admin_assigned_at = timezone.now()
            request.save()
            message = f"You have been reassigned to review the Sanctuary request: {request}"
            Notification.objects.create(
                user=new_admin,
                message=message,
                notification_type='sanctuary_admin_assignment',
                content_object=request,
                link=f"/sanctuary/vote/{request.id}/"
            )
            print(f"Admin reassigned to {new_admin.username} for Sanctuary request {request.id}")


#    ----------------------------------------
@shared_task
def check_for_inactive_appeal_admins():
    threshold_time = timezone.now() - timedelta(hours=24)
    inactive_appeals = SanctuaryOutcome.objects.filter(admin_assigned_at__lt=threshold_time, is_appealed=True, admin_reviewed=False)
    for outcome in inactive_appeals:
        admins = CustomUser.objects.filter(is_staff=True).exclude(id=outcome.assigned_admin.id)
        if admins.exists():
            new_admin = admins.order_by('?').first()
            outcome.assigned_admin = new_admin
            outcome.admin_assigned_at = timezone.now()
            outcome.save()
            message = f"You have been reassigned to review the appeal for Sanctuary outcome: {outcome}"
            Notification.objects.create(
                user=new_admin,
                message=message,
                notification_type='sanctuary_appeal_assignment',
                content_object=outcome,
                link=f"/sanctuary/outcome/{outcome.id}/appeal/"
            )
            print(f"Admin reassigned to {new_admin.username} for Sanctuary outcome appeal {outcome.id}")


#    ----------------------------------------
@shared_task
def check_appeal_deadlines():
    now = timezone.now()
    outcomes = SanctuaryOutcome.objects.filter(appeal_deadline__lt=now, is_appealed=False)
    for outcome in outcomes:
        finalize_sanctuary_outcome(outcome)
        logger.info(f"Sanctuary outcome {outcome.id} was finalized as the appeal deadline passed.")
