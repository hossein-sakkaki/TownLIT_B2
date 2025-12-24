# apps/main/services/policy_acceptance.py  (or wherever you prefer)
from django.utils import timezone
from django.db import transaction

from apps.main.models import TermsAndPolicy, UserAgreement

@transaction.atomic
def ensure_policy_acceptance(*, user, policy: TermsAndPolicy) -> UserAgreement:
    """
    Ensures user has a *fresh* acceptance for the given policy.
    - If latest exists AND latest.agreed_at >= policy.last_updated -> no-op
    - Else create a new latest agreement row (history preserved)
    """
    latest = (
        UserAgreement.objects
        .filter(user=user, policy=policy, is_latest_agreement=True)
        .order_by("-agreed_at")
        .first()
    )

    if latest:
        # if policy changed after user agreed -> must re-accept
        if policy.last_updated and latest.agreed_at and latest.agreed_at >= policy.last_updated:
            return latest

    # create a new acceptance event (save() will flip previous latest=False)
    return UserAgreement.objects.create(user=user, policy=policy, is_latest_agreement=True)
