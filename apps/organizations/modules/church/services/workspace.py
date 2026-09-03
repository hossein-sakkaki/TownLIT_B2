# apps/organizations/modules/church/services/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.db import transaction

from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchWorkspace
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


@transaction.atomic
def update_church_workspace(
    *,
    workspace,
    actor,
    timezone_override=None,
    membership_directory_enabled=None,
    attendance_tracking_enabled=None,
    default_gathering_duration_minutes=None,
    settings=None,
):
    workspace = (
        ChurchWorkspace.objects
        .select_for_update()
        .select_related(
            "activation__organization",
            "activation__module",
        )
        .get(pk=workspace.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_WORKSPACE,
    )

    if timezone_override is not None:
        workspace.timezone_override = timezone_override or None
    if membership_directory_enabled is not None:
        workspace.membership_directory_enabled = membership_directory_enabled
    if attendance_tracking_enabled is not None:
        workspace.attendance_tracking_enabled = attendance_tracking_enabled
    if default_gathering_duration_minutes is not None:
        workspace.default_gathering_duration_minutes = (
            default_gathering_duration_minutes
        )
    if settings is not None:
        workspace.settings = settings

    workspace.full_clean()
    workspace.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.WORKSPACE_UPDATED,
        actor=actor,
        entity=workspace,
    )

    return workspace
