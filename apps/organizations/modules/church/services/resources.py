# apps/organizations/modules/church/services/resources.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchPermissionKey,
    ChurchResourceReservationStatus,
    ChurchResourceStatus,
)
from apps.organizations.modules.church.models import (
    ChurchResource,
    ChurchResourceReservation,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit
from apps.organizations.modules.church.services.slugs import unique_workspace_slug


def _max_concurrent_reserved_quantity(*, resource) -> int:
    reservations = list(
        ChurchResourceReservation.objects
        .filter(
            resource=resource,
            status=ChurchResourceReservationStatus.RESERVED,
        )
        .values_list("starts_at", "ends_at", "quantity")
    )

    events = []
    for starts_at, ends_at, quantity in reservations:
        events.append((starts_at, 1, int(quantity)))
        # Process endings before starts at the same instant.
        events.append((ends_at, 0, -int(quantity)))

    current = 0
    maximum = 0
    for _, _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        current += delta
        maximum = max(maximum, current)

    return maximum


@transaction.atomic
def create_church_resource(
    *,
    workspace,
    actor,
    resource_type,
    name,
    campus=None,
    ministry=None,
    description=None,
    is_reservable=True,
    quantity_available=1,
    capacity=None,
    sort_order=100,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_RESOURCES,
    )

    resource = ChurchResource(
        workspace=workspace,
        campus=campus,
        ministry=ministry,
        resource_type=resource_type,
        name=name,
        slug=unique_workspace_slug(
            model=ChurchResource,
            workspace=workspace,
            name=name,
        ),
        description=description,
        is_reservable=is_reservable,
        quantity_available=quantity_available,
        capacity=capacity,
        sort_order=sort_order,
    )
    resource.full_clean()
    resource.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.RESOURCE_CREATED,
        actor=actor,
        entity=resource,
        metadata={"resource_type": resource.resource_type},
    )

    return resource


@transaction.atomic
def update_church_resource(*, resource, actor, **changes):
    resource = (
        ChurchResource.objects
        .select_for_update()
        .select_related("workspace__activation__organization", "campus", "ministry")
        .get(pk=resource.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=resource.workspace,
        permission_key=ChurchPermissionKey.MANAGE_RESOURCES,
    )

    allowed = {
        "resource_type",
        "name",
        "campus",
        "ministry",
        "description",
        "status",
        "is_reservable",
        "quantity_available",
        "capacity",
        "sort_order",
    }

    for field, value in changes.items():
        if field not in allowed:
            raise ValidationError(f"Unsupported Church resource field: {field}.")
        setattr(resource, field, value)

    if "name" in changes:
        resource.slug = unique_workspace_slug(
            model=ChurchResource,
            workspace=resource.workspace,
            name=resource.name,
            exclude_pk=resource.pk,
        )

    if "quantity_available" in changes:
        required_quantity = _max_concurrent_reserved_quantity(resource=resource)
        if int(resource.quantity_available) < required_quantity:
            raise ValidationError(
                "Resource quantity cannot be reduced below current reservation demand."
            )

    resource.full_clean()
    resource.save()

    record_church_audit(
        workspace=resource.workspace,
        event=ChurchAuditEvent.RESOURCE_UPDATED,
        actor=actor,
        entity=resource,
    )

    return resource


@transaction.atomic
def reserve_church_resource(
    *,
    resource,
    occurrence,
    actor,
    quantity=1,
    starts_at=None,
    ends_at=None,
    notes=None,
):
    resource = (
        ChurchResource.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=resource.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=resource.workspace,
        permission_key=ChurchPermissionKey.MANAGE_RESOURCES,
    )

    if resource.status != ChurchResourceStatus.ACTIVE:
        raise ValidationError("Only active Church resources can be reserved.")
    if not resource.is_reservable:
        raise ValidationError("This Church resource is not reservable.")
    if occurrence.workspace_id != resource.workspace_id:
        raise ValidationError("Resource and gathering must belong to the same Church workspace.")

    starts_at = starts_at or occurrence.starts_at
    ends_at = ends_at or occurrence.ends_at

    if ends_at <= starts_at:
        raise ValidationError("Resource reservation end time must be after start time.")

    existing = ChurchResourceReservation.objects.filter(
        resource=resource,
        occurrence=occurrence,
    ).first()

    if existing:
        if existing.status == ChurchResourceReservationStatus.RESERVED:
            return existing
        existing.quantity = quantity
        existing.starts_at = starts_at
        existing.ends_at = ends_at
        existing.status = ChurchResourceReservationStatus.RESERVED
        existing.reserved_by = actor
        existing.canceled_at = None
        existing.canceled_by = None
        existing.completed_at = None
        existing.completed_by = None
        existing.notes = notes
        reservation = existing
    else:
        reservation = ChurchResourceReservation(
            resource=resource,
            occurrence=occurrence,
            quantity=quantity,
            starts_at=starts_at,
            ends_at=ends_at,
            reserved_by=actor,
            notes=notes,
        )

    reservation.full_clean()

    overlapping_quantity = (
        ChurchResourceReservation.objects
        .filter(
            resource=resource,
            status=ChurchResourceReservationStatus.RESERVED,
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        )
        .exclude(pk=reservation.pk)
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    if overlapping_quantity + quantity > resource.quantity_available:
        raise ValidationError(
            "Church resource capacity is not available for the requested time window."
        )

    reservation.save()

    record_church_audit(
        workspace=resource.workspace,
        event=ChurchAuditEvent.RESOURCE_RESERVED,
        actor=actor,
        entity=reservation,
        metadata={
            "resource_public_id": str(resource.public_id),
            "occurrence_public_id": str(occurrence.public_id),
            "quantity": quantity,
        },
    )

    return reservation


@transaction.atomic
def cancel_church_resource_reservation(*, reservation, actor, now=None):
    now = now or timezone.now()
    reservation = (
        ChurchResourceReservation.objects
        .select_for_update()
        .select_related("resource__workspace__activation__organization", "occurrence")
        .get(pk=reservation.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=reservation.resource.workspace,
        permission_key=ChurchPermissionKey.MANAGE_RESOURCES,
    )

    if reservation.status == ChurchResourceReservationStatus.CANCELED:
        return reservation
    if reservation.status == ChurchResourceReservationStatus.COMPLETED:
        raise ValidationError("Completed resource reservations cannot be canceled.")

    reservation.status = ChurchResourceReservationStatus.CANCELED
    reservation.canceled_at = now
    reservation.canceled_by = actor
    reservation.full_clean()
    reservation.save(
        update_fields=["status", "canceled_at", "canceled_by", "updated_at"]
    )

    record_church_audit(
        workspace=reservation.resource.workspace,
        event=ChurchAuditEvent.RESOURCE_RESERVATION_CANCELED,
        actor=actor,
        entity=reservation,
    )

    return reservation


@transaction.atomic
def complete_church_resource_reservation(*, reservation, actor, now=None):
    now = now or timezone.now()
    reservation = (
        ChurchResourceReservation.objects
        .select_for_update()
        .select_related("resource__workspace__activation__organization", "occurrence")
        .get(pk=reservation.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=reservation.resource.workspace,
        permission_key=ChurchPermissionKey.MANAGE_RESOURCES,
    )

    if reservation.status == ChurchResourceReservationStatus.COMPLETED:
        return reservation
    if reservation.status != ChurchResourceReservationStatus.RESERVED:
        raise ValidationError("Only active resource reservations can be completed.")

    reservation.status = ChurchResourceReservationStatus.COMPLETED
    reservation.completed_at = now
    reservation.completed_by = actor
    reservation.full_clean()
    reservation.save(
        update_fields=["status", "completed_at", "completed_by", "updated_at"]
    )

    record_church_audit(
        workspace=reservation.resource.workspace,
        event=ChurchAuditEvent.RESOURCE_RESERVATION_COMPLETED,
        actor=actor,
        entity=reservation,
    )

    return reservation
