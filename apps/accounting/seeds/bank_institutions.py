# apps/accounting/seeds/bank_institutions.py

from apps.accounting.models import BankInstitution
from apps.accounting.config.bank_institutions import BANK_INSTITUTIONS


def seed_bank_institutions():
    """
    Create or update default bank institutions.
    Safe to run multiple times.
    """

    for item in BANK_INSTITUTIONS:
        BankInstitution.objects.update_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "institution_type": item["institution_type"],
                "country": item["country"],
                "swift_code": item["swift_code"],
                "website": item["website"],
                "support_phone": item["support_phone"],
                "support_email": item["support_email"],
                "note": item["note"],
                "is_active": True,
            },
        )