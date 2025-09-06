from django.db import transaction
from apps.profiles.models import Fellowship

from apps.profiles.constants import RECIPROCAL_FELLOWSHIP_CHOICES
import logging

logger = logging.getLogger(__name__)


# FELLOWSHIP Manager ----------------------------------------------------------
def add_symmetric_fellowship(from_user, to_user, fellowship_type, reciprocal_fellowship_type=None):
    from django.db import IntegrityError

    valid_types = [choice[0] for choice in RECIPROCAL_FELLOWSHIP_CHOICES]

    if fellowship_type not in valid_types or (reciprocal_fellowship_type and reciprocal_fellowship_type not in valid_types):
        logger.error("Invalid fellowship type provided.")
        return False

    try:
        with transaction.atomic():
            main_fellowship_exists = Fellowship.objects.filter(
                from_user=from_user,
                to_user=to_user,
                fellowship_type=fellowship_type,
                reciprocal_fellowship_type=reciprocal_fellowship_type
            ).exists()

            if not main_fellowship_exists:
                Fellowship.objects.create(
                    from_user=from_user,
                    to_user=to_user,
                    fellowship_type=fellowship_type,
                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                    status='Accepted'
                )
                logger.info(f"Fellowship created: {from_user} -> {to_user} ({fellowship_type})")

            # چک کردن وجود رابطه متقارن
            if reciprocal_fellowship_type:
                reciprocal_fellowship_exists = Fellowship.objects.filter(
                    from_user=to_user,
                    to_user=from_user,
                    fellowship_type=reciprocal_fellowship_type,
                    reciprocal_fellowship_type=fellowship_type
                ).exists()

                if not reciprocal_fellowship_exists:
                    Fellowship.objects.create(
                        from_user=to_user,
                        to_user=from_user,
                        fellowship_type=reciprocal_fellowship_type,
                        reciprocal_fellowship_type=fellowship_type,
                        status='Accepted'
                    )
                    logger.info(f"Reciprocal fellowship created: {to_user} -> {from_user} ({reciprocal_fellowship_type})")

        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while adding symmetric fellowship: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while adding symmetric fellowship: {e}")
        return False


def remove_symmetric_fellowship(from_user, to_user, relationship_type):
    try:
        with transaction.atomic():
            # Delete the main relationship
            main_deleted = Fellowship.objects.filter(
                from_user=from_user,
                to_user=to_user,
                fellowship_type=relationship_type,
                status='Accepted'
            ).delete()
            logger.info(f"Main fellowship removed: {from_user} -> {to_user} ({relationship_type})")

            # Delete the reciprocal relationship
            reciprocal_deleted = Fellowship.objects.filter(
                from_user=to_user,
                to_user=from_user,
                reciprocal_fellowship_type=relationship_type,
                status='Accepted'
            ).delete()
            logger.info(f"Reciprocal fellowship removed: {to_user} -> {from_user} ({relationship_type})")

        return True
    except Exception as e:
        logger.error(f"Error while removing symmetric fellowship: {e}")
        return False

