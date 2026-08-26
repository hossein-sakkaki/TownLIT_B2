# apps/bookstore_inventory/services/inventory_reports.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-24.

from __future__ import annotations

import logging
from collections import OrderedDict

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.asset_delivery.services.signers.cloudfront_signer import (
    build_signed_exact_url,
)
from apps.asset_delivery.utils.cdn_urls import build_cdn_url
from apps.bookstore_inventory.constants import WarehouseStaffRole
from apps.bookstore_inventory.models import (
    InventoryBalance,
    StockMovement,
    Warehouse,
    WarehouseStaffAssignment,
)
from utils.email.email_tools import send_custom_email


logger = logging.getLogger(__name__)

INVENTORY_REPORT_HTML_TEMPLATE = (
    "bookstore_inventory/email/"
    "inventory_movement_summary.html"
)

INVENTORY_REPORT_TEXT_TEMPLATE = (
    "bookstore_inventory/email/"
    "inventory_movement_summary.txt"
)

DEFAULT_RECIPIENT_ROLES = (
    WarehouseStaffRole.PRIMARY_MANAGER,
    WarehouseStaffRole.MANAGER,
)

DEFAULT_COVER_URL_TTL_SECONDS = 7 * 24 * 60 * 60

REPORT_SOURCE_STOCK_CHANGE = "stock_change"
REPORT_SOURCE_MANUAL = "manual"

VALID_REPORT_SOURCES = {
    REPORT_SOURCE_STOCK_CHANGE,
    REPORT_SOURCE_MANUAL,
}


def _email_cover_url(cover_image):
    """
    Return a temporary exact-resource CloudFront URL for an email cover.

    Book media remains private in storage. Email delivery reuses the
    canonical TownLIT CDN URL builder and CloudFront signer.
    """

    if not cover_image:
        return ""

    storage_key = str(
        getattr(cover_image, "name", "") or ""
    ).strip()

    if not storage_key:
        return ""

    cdn_url = build_cdn_url(storage_key)

    if not cdn_url:
        logger.warning(
            "bookstore.inventory_report."
            "cover_cdn_url_unavailable key=%s",
            storage_key,
        )
        return ""

    configured_ttl = int(
        getattr(
            settings,
            "BOOKSTORE_INVENTORY_REPORT_COVER_TTL_SECONDS",
            DEFAULT_COVER_URL_TTL_SECONDS,
        )
    )

    expires_in = max(
        3600,
        min(configured_ttl, 30 * 24 * 60 * 60),
    )

    try:
        result = build_signed_exact_url(
            resource_url=cdn_url,
            expires_in=expires_in,
        )
    except Exception:
        logger.exception(
            "bookstore.inventory_report."
            "cover_signing_failed key=%s",
            storage_key,
        )
        return ""

    return result.url


def _recipient_display_name(user):
    parts = [
        str(getattr(user, "name", "") or "").strip(),
        str(getattr(user, "family", "") or "").strip(),
    ]

    full_name = " ".join(
        part for part in parts if part
    )

    if full_name:
        return full_name

    get_full_name = getattr(user, "get_full_name", None)

    if callable(get_full_name):
        full_name = str(
            get_full_name() or ""
        ).strip()

        if full_name:
            return full_name

    return str(
        getattr(user, "username", "")
        or getattr(user, "email", "")
        or "Warehouse manager"
    )


def inventory_report_recipients(*, override_emails=None):
    """
    Return unique recipients for bookstore inventory status emails.

    Active primary managers and managers qualify through their current
    warehouse assignments, but every qualifying recipient receives the
    complete inventory snapshot for all active TownLIT warehouses.

    Explicit override recipients replace normal recipients and are intended
    for controlled tests or management-command usage.

    Configured extra recipients are added to the normal manager list.
    """

    if override_emails:
        recipients = OrderedDict()

        for raw_email in override_emails:
            email = str(raw_email or "").strip()

            if not email:
                continue

            recipients[email.casefold()] = {
                "email": email,
                "name": "Warehouse manager",
                "user_id": None,
            }

        return list(recipients.values())

    now = timezone.now()

    configured_roles = getattr(
        settings,
        "BOOKSTORE_INVENTORY_REPORT_RECIPIENT_ROLES",
        None,
    ) or DEFAULT_RECIPIENT_ROLES

    if isinstance(configured_roles, str):
        configured_roles = tuple(
            role.strip()
            for role in configured_roles.split(",")
            if role.strip()
        )

    assignments = (
        WarehouseStaffAssignment.objects.filter(
            warehouse__is_active=True,
            user__is_active=True,
            is_active=True,
            role__in=tuple(configured_roles),
            starts_at__lte=now,
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gt=now)
        )
        .exclude(user__email="")
        .select_related("user", "warehouse")
        .order_by("user_id", "warehouse_id", "pk")
    )

    recipients = OrderedDict()

    for assignment in assignments:
        email = str(
            getattr(assignment.user, "email", "")
            or ""
        ).strip()

        if not email:
            continue

        key = email.casefold()

        if key not in recipients:
            recipients[key] = {
                "email": email,
                "name": _recipient_display_name(
                    assignment.user
                ),
                "user_id": assignment.user_id,
            }

    extra_recipients = getattr(
        settings,
        "BOOKSTORE_INVENTORY_REPORT_EXTRA_RECIPIENTS",
        (),
    )

    if isinstance(extra_recipients, str):
        extra_recipients = extra_recipients.split(",")

    for raw_email in extra_recipients:
        email = str(raw_email or "").strip()

        if not email:
            continue

        key = email.casefold()

        if key not in recipients:
            recipients[key] = {
                "email": email,
                "name": "Bookstore administrator",
                "user_id": None,
            }

    return list(recipients.values())


def build_inventory_snapshot(*, generated_at=None):
    """
    Build the complete current inventory snapshot.

    Every active TownLIT warehouse is always included. This email service
    intentionally does not support warehouse-scoped snapshots.
    """

    generated_at = generated_at or timezone.now()

    warehouses = list(
        Warehouse.objects.filter(
            is_active=True
        ).order_by("name", "pk")
    )

    warehouse_ids = [
        warehouse.pk
        for warehouse in warehouses
    ]

    balances = (
        InventoryBalance.objects.filter(
            warehouse_id__in=warehouse_ids,
        )
        .select_related(
            "warehouse",
            "book_edition__book",
        )
        .order_by(
            "warehouse__name",
            "book_edition__book__title",
            "book_edition__edition_code",
        )
    )

    balances_by_warehouse = {
        warehouse.pk: []
        for warehouse in warehouses
    }

    for balance in balances:
        balances_by_warehouse.setdefault(
            balance.warehouse_id,
            [],
        ).append(balance)

    warehouse_rows = []
    cover_url_cache = {}

    grand_totals = {
        "warehouse_count": len(warehouses),
        "edition_count": 0,
        "on_hand": 0,
        "reserved": 0,
        "unavailable": 0,
        "available": 0,
    }

    for warehouse in warehouses:
        items = []

        totals = {
            "edition_count": 0,
            "on_hand": 0,
            "reserved": 0,
            "unavailable": 0,
            "available": 0,
        }

        for balance in balances_by_warehouse.get(
            warehouse.pk,
            [],
        ):
            edition = balance.book_edition
            cover_image = edition.effective_cover_image

            cover_key = str(
                getattr(cover_image, "name", "")
                or ""
            ).strip()

            if cover_key not in cover_url_cache:
                cover_url_cache[cover_key] = (
                    _email_cover_url(cover_image)
                    if cover_key
                    else ""
                )

            items.append({
                "book": edition.book.title,
                "book_type": (
                    edition.book.get_book_type_display()
                ),
                "edition": edition.edition_code,
                "language": edition.language,
                "cover_url": cover_url_cache.get(
                    cover_key,
                    "",
                ),
                "on_hand": balance.on_hand_quantity,
                "reserved": balance.reserved_quantity,
                "unavailable": balance.unavailable_quantity,
                "available": balance.available_quantity,
            })

            totals["edition_count"] += 1
            totals["on_hand"] += balance.on_hand_quantity
            totals["reserved"] += balance.reserved_quantity
            totals["unavailable"] += balance.unavailable_quantity
            totals["available"] += balance.available_quantity

        for key in (
            "edition_count",
            "on_hand",
            "reserved",
            "unavailable",
            "available",
        ):
            grand_totals[key] += totals[key]

        warehouse_rows.append({
            "name": warehouse.name,
            "code": warehouse.code,
            "items": items,
            "totals": totals,
        })

    local_generated_at = timezone.localtime(
        generated_at
    )

    return {
        "generated_at": local_generated_at,
        "report_date": local_generated_at.date(),
        "current_year": local_generated_at.year,
        "warehouses": warehouse_rows,
        "grand_totals": grand_totals,
    }


def _resolved_movement_ids(movement_ids):
    requested_ids = {
        int(movement_id)
        for movement_id in (movement_ids or [])
        if movement_id
    }

    if not requested_ids:
        return []

    return list(
        StockMovement.objects.filter(
            pk__in=requested_ids
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def send_inventory_summary(
    *,
    movement_ids=None,
    source=REPORT_SOURCE_STOCK_CHANGE,
    override_emails=None,
    dry_run=False,
):
    """
    Send the complete current inventory snapshot.

    Automatic sends are triggered by committed stock changes.
    Manual sends use the exact same reporting and delivery pipeline.
    """

    source = str(
        source or REPORT_SOURCE_STOCK_CHANGE
    ).strip()

    if source not in VALID_REPORT_SOURCES:
        raise ValueError(
            f"Unsupported inventory report source: {source}"
        )

    resolved_movement_ids = _resolved_movement_ids(
        movement_ids
    )

    if (
        source == REPORT_SOURCE_STOCK_CHANGE
        and not resolved_movement_ids
    ):
        logger.warning(
            "bookstore.inventory_report."
            "automatic_send_without_valid_movements"
        )

        return {
            "status": "no_movements",
            "recipients": 0,
            "sent": 0,
            "failed": 0,
        }

    recipients = inventory_report_recipients(
        override_emails=override_emails
    )

    if not recipients:
        logger.warning(
            "bookstore.inventory_report.no_recipients"
        )

        return {
            "status": "no_recipients",
            "recipients": 0,
            "sent": 0,
            "failed": 0,
        }

    generated_at = timezone.now()
    snapshot = build_inventory_snapshot(
        generated_at=generated_at
    )

    if dry_run:
        return {
            "status": "dry_run",
            "source": source,
            "movement_count": len(
                resolved_movement_ids
            ),
            "recipients": len(recipients),
            "sent": 0,
            "failed": 0,
            "warehouse_count": (
                snapshot["grand_totals"][
                    "warehouse_count"
                ]
            ),
            "available": (
                snapshot["grand_totals"][
                    "available"
                ]
            ),
        }

    if source == REPORT_SOURCE_MANUAL:
        subject = (
            "TownLIT Current Bookstore Inventory"
        )
    else:
        subject = (
            "TownLIT Inventory Update"
        )

    sent = 0
    failed = 0

    for recipient in recipients:
        context = {
            **snapshot,
            "recipient_name": recipient["name"],
            "report_source": source,
            "movement_count": len(
                resolved_movement_ids
            ),
        }

        success = send_custom_email(
            to=recipient["email"],
            subject=subject,
            template_path=(
                INVENTORY_REPORT_HTML_TEMPLATE
            ),
            text_template_path=(
                INVENTORY_REPORT_TEXT_TEMPLATE
            ),
            context=context,
        )

        if success:
            sent += 1
            continue

        failed += 1

        logger.warning(
            "bookstore.inventory_report."
            "recipient_failed email=%s source=%s",
            recipient["email"],
            source,
        )

    status = (
        "sent"
        if failed == 0
        else "partial_failure"
    )

    logger.info(
        "bookstore.inventory_report.complete "
        "source=%s movements=%s recipients=%s "
        "sent=%s failed=%s",
        source,
        len(resolved_movement_ids),
        len(recipients),
        sent,
        failed,
    )

    return {
        "status": status,
        "source": source,
        "movement_count": len(
            resolved_movement_ids
        ),
        "recipients": len(recipients),
        "sent": sent,
        "failed": failed,
    }