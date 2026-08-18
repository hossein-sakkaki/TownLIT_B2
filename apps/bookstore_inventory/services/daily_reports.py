# apps/bookstore_inventory/services/daily_reports.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

import logging
from collections import OrderedDict

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.bookstore_inventory.constants import WarehouseStaffRole
from apps.bookstore_inventory.models import (
    InventoryBalance,
    Warehouse,
    WarehouseStaffAssignment,
)
from utils.email.email_tools import send_custom_email


logger = logging.getLogger(__name__)

DAILY_REPORT_HTML_TEMPLATE = (
    "bookstore_inventory/email/daily_inventory_summary.html"
)
DAILY_REPORT_TEXT_TEMPLATE = (
    "bookstore_inventory/email/daily_inventory_summary.txt"
)
DEFAULT_RECIPIENT_ROLES = (
    WarehouseStaffRole.PRIMARY_MANAGER,
    WarehouseStaffRole.MANAGER,
)


def _recipient_display_name(user):
    parts = [
        str(getattr(user, "name", "") or "").strip(),
        str(getattr(user, "family", "") or "").strip(),
    ]
    full_name = " ".join(part for part in parts if part)
    if full_name:
        return full_name
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = str(get_full_name() or "").strip()
        if full_name:
            return full_name
    return str(
        getattr(user, "username", "")
        or getattr(user, "email", "")
        or "Warehouse manager"
    )


def daily_report_recipients(*, override_emails=None):
    """Return unique, privacy-safe recipients for one daily delivery run."""

    if override_emails:
        recipients = OrderedDict()
        for raw_email in override_emails:
            email = str(raw_email or "").strip()
            if email:
                recipients[email.casefold()] = {
                    "email": email,
                    "name": "Warehouse manager",
                    "user_id": None,
                }
        return list(recipients.values())

    now = timezone.now()
    configured_roles = getattr(
        settings,
        "BOOKSTORE_DAILY_REPORT_RECIPIENT_ROLES",
        DEFAULT_RECIPIENT_ROLES,
    )
    if isinstance(configured_roles, str):
        configured_roles = tuple(
            role.strip()
            for role in configured_roles.split(",")
            if role.strip()
        )
    assignments = WarehouseStaffAssignment.objects.filter(
        warehouse__is_active=True,
        user__is_active=True,
        is_active=True,
        role__in=tuple(configured_roles),
        starts_at__lte=now,
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    ).exclude(
        user__email=""
    ).select_related("user").order_by("user_id", "pk")

    recipients = OrderedDict()
    for assignment in assignments:
        email = str(getattr(assignment.user, "email", "") or "").strip()
        if not email:
            continue
        recipients[email.casefold()] = {
            "email": email,
            "name": _recipient_display_name(assignment.user),
            "user_id": assignment.user_id,
        }

    extra_recipients = getattr(
        settings,
        "BOOKSTORE_DAILY_REPORT_EXTRA_RECIPIENTS",
        (),
    )
    if isinstance(extra_recipients, str):
        extra_recipients = extra_recipients.split(",")
    for raw_email in extra_recipients:
        email = str(raw_email or "").strip()
        if email:
            recipients.setdefault(email.casefold(), {
                "email": email,
                "name": "Bookstore administrator",
                "user_id": None,
            })
    return list(recipients.values())


def build_daily_inventory_snapshot(*, generated_at=None):
    """Build one concise all-warehouse snapshot without exposing addresses."""

    generated_at = generated_at or timezone.now()
    warehouses = list(Warehouse.objects.filter(is_active=True).order_by("name", "pk"))
    balances = InventoryBalance.objects.filter(
        warehouse__is_active=True,
        on_hand_quantity__gt=0,
    ).select_related(
        "warehouse", "book_edition__book"
    ).order_by(
        "warehouse__name", "book_edition__book__title", "book_edition__edition_code"
    )
    balances_by_warehouse = {warehouse.pk: [] for warehouse in warehouses}
    for balance in balances:
        balances_by_warehouse.setdefault(balance.warehouse_id, []).append(balance)

    warehouse_rows = []
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
        for balance in balances_by_warehouse.get(warehouse.pk, []):
            items.append({
                "book": balance.book_edition.book.title,
                "book_type": balance.book_edition.book.get_book_type_display(),
                "edition": balance.book_edition.edition_code,
                "language": balance.book_edition.language,
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
        for key in ("edition_count", "on_hand", "reserved", "unavailable", "available"):
            grand_totals[key] += totals[key]
        warehouse_rows.append({
            "name": warehouse.name,
            "code": warehouse.code,
            "items": items,
            "totals": totals,
        })

    local_generated_at = timezone.localtime(generated_at)
    return {
        "generated_at": local_generated_at,
        "report_date": local_generated_at.date(),
        "current_year": local_generated_at.year,
        "warehouses": warehouse_rows,
        "grand_totals": grand_totals,
    }


def send_daily_inventory_summary(*, override_emails=None, dry_run=False):
    """Send the snapshot once to each manager; failures are isolated per recipient."""

    if not getattr(settings, "BOOKSTORE_DAILY_REPORT_ENABLED", True):
        logger.info("bookstore.daily_inventory_report.disabled")
        return {"status": "disabled", "recipients": 0, "sent": 0, "failed": 0}

    recipients = daily_report_recipients(override_emails=override_emails)
    snapshot = build_daily_inventory_snapshot()
    if dry_run:
        return {
            "status": "dry_run",
            "recipients": len(recipients),
            "sent": 0,
            "failed": 0,
            "emails": [recipient["email"] for recipient in recipients],
            "warehouse_count": snapshot["grand_totals"]["warehouse_count"],
            "available": snapshot["grand_totals"]["available"],
        }
    if not recipients:
        logger.warning("bookstore.daily_inventory_report.no_recipients")
        return {"status": "no_recipients", "recipients": 0, "sent": 0, "failed": 0}

    subject = (
        "TownLIT Daily Bookstore Inventory — "
        f"{snapshot['report_date'].strftime('%B %d, %Y')}"
    )
    sent = 0
    failed = 0
    for recipient in recipients:
        context = {
            **snapshot,
            "recipient_name": recipient["name"],
        }
        success = send_custom_email(
            to=recipient["email"],
            subject=subject,
            template_path=DAILY_REPORT_HTML_TEMPLATE,
            text_template_path=DAILY_REPORT_TEXT_TEMPLATE,
            context=context,
        )
        if success:
            sent += 1
        else:
            failed += 1
            logger.warning(
                "bookstore.daily_inventory_report.recipient_failed email=%s",
                recipient["email"],
            )

    status = "sent" if failed == 0 else "partial_failure"
    logger.info(
        "bookstore.daily_inventory_report.complete recipients=%s sent=%s failed=%s",
        len(recipients),
        sent,
        failed,
    )
    return {
        "status": status,
        "recipients": len(recipients),
        "sent": sent,
        "failed": failed,
    }
