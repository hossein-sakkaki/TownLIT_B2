# apps/bookstore_inventory/services/access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.bookstore_inventory.models import WarehouseStaffAssignment


CAN_RECEIVE_STOCK = "can_receive_stock"
CAN_FULFILL_ORDERS = "can_fulfill_orders"
CAN_TRANSFER_STOCK = "can_transfer_stock"
CAN_COUNT_STOCK = "can_count_stock"
CAN_ADJUST_STOCK = "can_adjust_stock"
CAN_PROCESS_RETURNS = "can_process_returns"


def current_warehouse_ids(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    now = timezone.now()
    return list(
        WarehouseStaffAssignment.objects.filter(
            user=user,
            is_active=True,
            starts_at__lte=now,
        ).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gt=now)
        ).values_list("warehouse_id", flat=True)
    )


def require_warehouse_capability(*, user, warehouse, capability, permission=None):
    """Require current operational responsibility for an irreversible action.

    A ``None`` user is reserved for trusted internal jobs and tests. Superusers
    bypass warehouse scope, while ordinary staff require both the normal Django
    permission (checked by Admin) and this warehouse assignment check.
    """

    if user is None or getattr(user, "is_superuser", False):
        return None
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        raise ValidationError("An active authenticated user is required for this operation.")
    if permission and not user.has_perm(permission):
        raise ValidationError(
            f"You do not have the required Django permission: {permission}."
        )

    now = timezone.now()
    assignment = WarehouseStaffAssignment.objects.select_related(
        "warehouse", "user"
    ).filter(
        warehouse=warehouse,
        user=user,
        is_active=True,
        starts_at__lte=now,
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    ).first()

    if assignment is None or not assignment.allows(capability):
        raise ValidationError(
            f"You are not assigned the required operational capability for "
            f"warehouse '{warehouse}'."
        )
    return assignment


def require_capability_for_warehouses(*, user, warehouses, capability, permission=None):
    checked = set()
    assignments = []
    for warehouse in warehouses:
        if warehouse.pk in checked:
            continue
        checked.add(warehouse.pk)
        assignment = require_warehouse_capability(
            user=user,
            warehouse=warehouse,
            capability=capability,
            permission=permission,
        )
        if assignment is not None:
            assignments.append(assignment)
    return assignments
