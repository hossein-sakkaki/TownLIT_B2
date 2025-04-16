from celery import shared_task
from django.utils import timezone
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import F, Count
from django.db import transaction
from .models import Organization
from apps.notifications.models import Notification
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# DELETE USERS ACCOUNTS ----------------------------------------------------------------------------------------------------
@shared_task
def delete_inactive_entities():
    three_months_ago = timezone.now() - timedelta(days=90)
    delete_inactive_model(Organization, three_months_ago, delete_custom_user=False)

def delete_inactive_model(model_class, threshold_date, delete_custom_user=False):
    entities_to_delete = model_class.objects.filter(
        is_active=False,
        deletion_requested_at__lte=threshold_date
    ).exclude(
        restoration_votes__count__gte=(F('org_owners__count') / 2)
    )  # Exclude entities with enough votes for restoration
    with transaction.atomic():
        for entity in entities_to_delete:
            if delete_custom_user:
                custom_user = entity.name
                entity.delete()
                custom_user.delete()
            else:
                entity.delete()
    return f'{entities_to_delete.count()} inactive {model_class.__name__.lower()}s deleted.'


# SEND NOTIFICATION FOR SINGLE OWNER ORGANIZATION ----------------------------------------------------------------------------
@shared_task
def notify_single_owner_organizations():
    single_owner_orgs = Organization.objects.annotate(owner_count=Count('org_owners')).filter(owner_count=1, is_suspended=False)
    for org in single_owner_orgs:
        last_notified = org.last_notified
        if not last_notified or (now() - last_notified) > timedelta(days=90):
            owner = org.org_owners.first()
            message = f"It is recommended to have at least 3 owners for better management of your organization '{org.org_name}'."
            Notification.objects.create(
                user=owner,
                message=message,
                notification_type='organization_management',
                link=f"/organizations/{org.slug}/owners/"
            )
            org.last_notified = now()
            org.save()
            