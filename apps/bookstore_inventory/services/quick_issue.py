# apps/bookstore_inventory/services/quick_issue.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    DeliveryMethod,
    OrderStatus,
    OrderType,
    PaymentStatus,
    RecipientType,
)
from apps.bookstore_inventory.models import (
    BookEdition,
    BookOrder,
    BookOrderItem,
    PaymentRecord,
)
from apps.bookstore_inventory.services.inventory import (
    fulfill_book_order,
)
from apps.bookstore_inventory.services.ledger import (
    sync_order_payment_to_ledger,
)


ALLOWED_QUICK_ISSUE_TYPES = {
    OrderType.FREE_DISTRIBUTION,
    OrderType.SALE,
}


@transaction.atomic
def create_and_post_quick_issue(
    *,
    user,
    warehouse,
    issue_at,
    issue_type,
    purpose,
    recipient_type,
    recipient_name,
    recipient_organization=None,
    currency="CAD",
    payment_method=None,
    transaction_reference="",
    notes="",
    items,
):
    """
    Create and immediately fulfil a simple bookstore issue.

    This is intentionally a thin workflow over BookOrder. It does not create
    a parallel inventory document type.

    Supported workflows:
    - immediate free distribution;
    - immediate fully-paid sale.

    Complex orders must continue through the full BookOrder workflow.
    """

    if issue_type not in ALLOWED_QUICK_ISSUE_TYPES:
        raise ValidationError(
            "Unsupported quick issue type."
        )

    if not warehouse.is_active:
        raise ValidationError(
            "The selected warehouse is inactive."
        )

    if timezone.is_naive(issue_at):
        issue_at = timezone.make_aware(
            issue_at,
            timezone.get_current_timezone(),
        )

    if issue_at > timezone.now():
        raise ValidationError(
            "Issue date and time cannot be in the future."
        )

    recipient_name = str(
        recipient_name
        or ""
    ).strip()

    if not recipient_name:
        raise ValidationError(
            "Recipient or destination is required."
        )

    currency = str(
        currency
        or "CAD"
    ).strip().upper()

    if not currency:
        currency = "CAD"

    item_rows = list(
        items
    )

    if not item_rows:
        raise ValidationError(
            "Add at least one book."
        )

    order_kwargs = {
        "order_type": issue_type,
        "status": OrderStatus.DRAFT,
        "recipient_type": recipient_type,
        "delivery_method": (
            DeliveryMethod.HAND_DELIVERY
        ),
        "purpose": purpose,
        "destination_name": (
            recipient_name
        ),
        "currency": currency,
        "created_by": user,
        "notes": str(
            notes
            or ""
        ).strip(),
    }

    if (
        recipient_type
        == RecipientType.ORGANIZATION
    ):
        order_kwargs.update({
            "recipient_organization": (
                recipient_organization
            ),
            "organization_name": (
                recipient_name
            ),
        })

    elif recipient_type == RecipientType.PERSON:
        order_kwargs.update({
            "recipient_first_name": (
                recipient_name
            ),
        })

    else:
        raise ValidationError(
            "Recipient type is invalid."
        )

    order = BookOrder(
        **order_kwargs
    )

    order.full_clean()
    order.save()

    for row in item_rows:
        submitted_edition = row.get(
            "book_edition"
        )

        if submitted_edition is None:
            continue

        edition = (
            BookEdition.objects
            .select_for_update()
            .select_related(
                "book"
            )
            .get(
                pk=submitted_edition.pk
            )
        )

        if not edition.is_active:
            raise ValidationError(
                f"'{edition}' is inactive."
            )

        quantity = int(
            row.get("quantity")
            or 0
        )

        if quantity <= 0:
            raise ValidationError(
                (
                    f"Quantity for '{edition}' "
                    "must be greater than zero."
                )
            )

        if (
            issue_type
            == OrderType.FREE_DISTRIBUTION
        ):
            if not edition.is_distributable:
                raise ValidationError(
                    (
                        f"'{edition}' is not enabled "
                        "for distribution."
                    )
                )

            unit_price = Decimal(
                "0.00"
            )

        else:
            if not edition.is_sellable:
                raise ValidationError(
                    (
                        f"'{edition}' is not enabled "
                        "for sale."
                    )
                )

            submitted_price = row.get(
                "unit_price"
            )

            unit_price = (
                submitted_price
                if submitted_price is not None
                else (
                    edition.fixed_price
                    or Decimal("0.00")
                )
            )

            if unit_price <= 0:
                raise ValidationError(
                    (
                        f"Enter a selling price for "
                        f"'{edition}'."
                    )
                )

        item = BookOrderItem(
            order=order,
            book_edition=edition,
            warehouse=warehouse,
            location=None,
            quantity=quantity,
            unit_price=unit_price,
            pricing_mode_snapshot=(
                edition.pricing_mode
            ),
        )

        item.full_clean()
        item.save()

    if not order.items.exists():
        raise ValidationError(
            "Add at least one book."
        )

    order.recalculate_totals(
        save=True
    )

    if issue_type == OrderType.SALE:
        if order.total_amount <= 0:
            raise ValidationError(
                (
                    "A paid sale must have a "
                    "positive total amount."
                )
            )

        if not payment_method:
            raise ValidationError(
                (
                    "Payment method is required "
                    "for a paid sale."
                )
            )

        payment = PaymentRecord(
            order=order,
            amount=order.total_amount,
            currency=currency,
            payment_method=payment_method,
            payment_status=PaymentStatus.PAID,
            transaction_reference=str(
                transaction_reference
                or ""
            ).strip(),
            received_by=user,
            received_at=issue_at,
            notes=(
                "Recorded through Quick Issue."
            ),
        )

        payment.full_clean()
        payment.save()

        # Safe even when another integration layer also calls this helper,
        # because the ledger service uses update_or_create with a unique key.
        sync_order_payment_to_ledger(
            payment
        )

        order.recalculate_totals(
            save=True
        )

    fulfill_book_order(
        order_id=order.pk,
        user=user,
        performed_at=issue_at,
    )

    order.refresh_from_db()

    return order