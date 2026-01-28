# apps/profiles/services/symmetric_friendship.py

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.profiles.models import Friendship
import logging

logger = logging.getLogger(__name__)


# FRIENDSHIP Manager ----------------------------------------------------------
def add_symmetric_friendship(user1, user2):
    try:
        with transaction.atomic():
            existing_friendship = Friendship.objects.filter(
                from_user=user1,
                to_user=user2,
                status='accepted'
            )
            if not existing_friendship.exists():
                Friendship.objects.create(from_user=user1, to_user=user2, status='accepted')

            # Check if the reverse accepted friendship exists
            reverse_friendship = Friendship.objects.filter(
                from_user=user2,
                to_user=user1,
                status='accepted'
            )
            if not reverse_friendship.exists():
                # Create a new reverse friendship
                Friendship.objects.create(from_user=user2, to_user=user1, status='accepted')

        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while creating friendship between {user1} and {user2}: {e}")
        return False


def remove_symmetric_friendship(initiator, counterpart):
    try:
        with transaction.atomic():
            # Update the friendship initiated by the initiator
            initiator_friendship = Friendship.objects.filter(
                from_user=initiator, to_user=counterpart, status='accepted'
            ).first()
            if initiator_friendship:
                initiator_friendship.status = 'deleted'
                initiator_friendship.deleted_at = timezone.now()
                initiator_friendship.is_active = False
                initiator_friendship.save()

            # Delete the friendship initiated by the counterpart
            counterpart_friendship = Friendship.objects.filter(
                from_user=counterpart, to_user=initiator, status='accepted'
            ).first()
            if counterpart_friendship:
                counterpart_friendship.delete()

        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while updating friendship status between {initiator} and {counterpart}: {e}")
        return False
    



