from celery import shared_task
import logging
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import Friendship, GuestUser, Member
from .services import remove_symmetric_friendship
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

logger = logging.getLogger(__name__)


# Delete Users Accounts ----------------------------------------------------------------------------------
@shared_task
def delete_inactive_entities():
    one_year_ago = timezone.now() - timedelta(days=365)
    delete_inactive_model(Member, one_year_ago, delete_custom_user=True)    
    delete_inactive_model(GuestUser, one_year_ago, delete_custom_user=True)    

def delete_inactive_model(model_class, threshold_date, delete_custom_user=False):
    entities_to_delete = model_class.objects.filter(is_active=False, deletion_requested_at__lte=threshold_date)

    with transaction.atomic():
        for entity in entities_to_delete:
            if delete_custom_user:
                custom_user = entity.name
                entity.delete()
                custom_user.delete()
            else:
                entity.delete()

    return f'{entities_to_delete.count()} inactive {model_class.__name__.lower()}s deleted.'

