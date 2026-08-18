# apps/bookstore_inventory/models/warehouse.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.bookstore_inventory.constants import LocationType, WarehouseStaffRole
from apps.bookstore_inventory.models.base import TimeStampedModel


class Warehouse(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True, db_index=True)
    province_state = models.CharField(max_length=120, blank=True, db_index=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=120, blank=True, default="Canada")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="WarehouseStaffAssignment",
        related_name="bookstore_warehouses",
        blank=True,
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        parts = (
            self.address_line_1, self.address_line_2, self.city,
            self.province_state, self.postal_code, self.country,
        )
        return ", ".join(part for part in parts if part)


class WarehouseStaffAssignment(TimeStampedModel):
    """Operational responsibility for one warehouse.

    Django permissions remain the first security layer. Service functions also
    require a current assignment with the relevant warehouse capability.
    """

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="staff_assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookstore_warehouse_assignments",
    )
    role = models.CharField(
        max_length=24,
        choices=WarehouseStaffRole.choices,
        default=WarehouseStaffRole.OPERATOR,
        db_index=True,
    )
    can_receive_stock = models.BooleanField(default=False)
    can_fulfill_orders = models.BooleanField(default=False)
    can_transfer_stock = models.BooleanField(default=False)
    can_count_stock = models.BooleanField(default=False)
    can_adjust_stock = models.BooleanField(default=False)
    can_process_returns = models.BooleanField(default=False)
    starts_at = models.DateTimeField(default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("warehouse__name", "role", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("warehouse", "user"),
                name="bookstore_unique_warehouse_staff_assignment",
            ),
            models.CheckConstraint(
                check=Q(ends_at__isnull=True) | Q(ends_at__gt=F("starts_at")),
                name="bookstore_warehouse_assignment_valid_dates",
            ),
        ]
        indexes = [
            models.Index(fields=("warehouse", "is_active")),
            models.Index(fields=("user", "is_active")),
        ]
        verbose_name = "Warehouse staff assignment"
        verbose_name_plural = "Warehouse staff assignments"

    def __str__(self):
        return f"{self.warehouse} — {self.user} ({self.get_role_display()})"

    def clean(self):
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End time must be after the start time."})

    @property
    def is_current(self):
        now = timezone.now()
        return bool(
            self.is_active
            and self.starts_at <= now
            and (self.ends_at is None or self.ends_at > now)
            and getattr(self.user, "is_active", True)
        )

    def allows(self, capability):
        if not self.is_current or self.role == WarehouseStaffRole.AUDITOR:
            return False
        if self.role in {
            WarehouseStaffRole.PRIMARY_MANAGER,
            WarehouseStaffRole.MANAGER,
        }:
            return True
        return bool(getattr(self, capability, False))


class WarehouseLocation(TimeStampedModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="locations")
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children",
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    location_type = models.CharField(
        max_length=24, choices=LocationType.choices, default=LocationType.SHELF,
    )
    is_pickable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("warehouse__name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("warehouse", "code"),
                name="bookstore_unique_location_code_per_warehouse",
            )
        ]
        verbose_name = "Warehouse location"
        verbose_name_plural = "Warehouse locations"

    def __str__(self):
        return f"{self.warehouse.code} / {self.code} — {self.name}"

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "A location cannot contain itself."})
            if self.parent.warehouse_id != self.warehouse_id:
                raise ValidationError({"parent": "Parent and child must belong to the same warehouse."})

