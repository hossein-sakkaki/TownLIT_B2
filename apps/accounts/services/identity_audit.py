# apps/accounts/services/identity_audit.py

from apps.accounts.models import IdentityAuditLog

def log_identity_event(
    *,
    user,
    action,
    source,
    identity_verification=None,
    actor=None,
    reason=None,
    previous_status=None,
    new_status=None,
    metadata=None,
):
    # Create immutable audit log entry
    IdentityAuditLog.objects.create(
        user=user,
        identity_verification=identity_verification,
        action=action,
        source=source,
        actor=actor,
        reason=reason,
        previous_status=previous_status,
        new_status=new_status,
        metadata=metadata or {},
    )
