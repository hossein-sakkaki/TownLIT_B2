# apps/accounting/services/entry_number.py

from django.utils import timezone


def generate_entry_number() -> str:
    """
    Generate a reasonably unique journal entry number.
    """

    now = timezone.now()
    return now.strftime("JE-%Y%m%d-%H%M%S-%f")