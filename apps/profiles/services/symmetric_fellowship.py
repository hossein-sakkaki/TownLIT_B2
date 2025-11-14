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


def remove_symmetric_fellowship(from_user, to_user, relationship_type) -> bool:
    """
    Unpair an accepted fellowship in both directions.
    Strategy:
      - Lock both rows.
      - Choose ONE row as the "notifying row" -> set status='Cancelled' + save() to trigger signal.
      - Delete notifying row and the reciprocal row.
      - If main row missing but reciprocal exists, flip the logic.
    Returns True on success (even if some sides were already missing).
    """
    try:
        with transaction.atomic():
            # Lock both directions if they exist
            main = (Fellowship.objects
                    .select_for_update()
                    .filter(from_user=from_user,
                            to_user=to_user,
                            fellowship_type=relationship_type,
                            status='Accepted')
                    .first())

            reciprocal = (Fellowship.objects
                          .select_for_update()
                          .filter(from_user=to_user,
                                  to_user=from_user,
                                  reciprocal_fellowship_type=relationship_type,
                                  status='Accepted')
                          .first())

            # If neither exists, nothing to do
            if not main and not reciprocal:
                logger.info("No active fellowship rows to remove.")
                return True

            # Prefer to notify via 'main'. If missing, notify via 'reciprocal'.
            notifying = main or reciprocal
            other = reciprocal if notifying is main else main

            # 1) Trigger exactly one notification burst
            notifying.status = 'Cancelled'
            notifying.save(update_fields=['status'])  # ✅ post_save → sends notif to both sides

            # 2) Cleanup: delete notifying row
            notifying.delete()

            # 3) Cleanup: delete the other side quietly (no save → no duplicate notif)
            if other:
                other.delete()

            logger.info(f"Fellowship unpaired: {from_user.id} ↔ {to_user.id} ({relationship_type})")
            return True

    except Exception as e:
        logger.error(f"Error while removing symmetric fellowship: {e}", exc_info=True)
        return False