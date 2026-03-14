# apps/accounts/services/townlit_verification_audit.py

from apps.accounts.models.townlit_verification import TownlitVerificationAuditLog


def log_townlit_verification_event(
    *,
    member,
    action,
    source,
    actor=None,
    reason=None,
    previous_status=None,
    new_status=None,
    metadata=None,
):
    TownlitVerificationAuditLog.objects.create(
        member=member,
        user=member.user,
        action=action,
        source=source,
        actor=actor,
        reason=reason,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata or {},
    )