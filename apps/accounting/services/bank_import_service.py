# apps/accounting/services/bank_import_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import csv
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path

from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.accounting.models import (
    BankAccount,
    BankReconciliationSession,
    BankStatementImport,
    BankStatementLine,
)


MONEY_QUANT = Decimal("0.01")


class BankImportError(Exception):
    """Raised when bank import fails."""

    pass


class CSVBankImportService:
    """
    Import bank statement lines from CSV.
    """

    REQUIRED_COLUMNS = {
        "transaction_date",
        "description",
        "amount",
    }

    def import_csv(
        self,
        *,
        statement_import: BankStatementImport,
    ) -> int:
        if not statement_import.source_file:
            raise BankImportError("No source file attached.")

        raw_bytes = self._read_source_bytes(statement_import)
        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        parsed_rows = self._parse_csv(raw_bytes)

        if not parsed_rows:
            raise BankImportError("The CSV file contains no transaction rows.")

        period_start = min(
            row["transaction_date"]
            for row in parsed_rows
        )

        period_end = max(
            row["transaction_date"]
            for row in parsed_rows
        )

        started_processing = False

        try:
            with db_transaction.atomic():
                current = (
                    BankStatementImport.objects
                    .select_for_update()
                    .select_related("bank_account")
                    .get(pk=statement_import.pk)
                )

                BankAccount.objects.select_for_update().get(
                    pk=current.bank_account_id
                )

                self._validate_import_state(current)

                if current.lines.exists():
                    raise BankImportError(
                        "This statement import already contains transaction lines."
                    )

                duplicate_file_exists = (
                    BankStatementImport.objects
                    .filter(
                        bank_account_id=current.bank_account_id,
                        file_hash=file_hash,
                    )
                    .exclude(pk=current.pk)
                    .exists()
                )

                if duplicate_file_exists:
                    raise BankImportError(
                        "This bank statement file has already been imported."
                    )

                self._assert_period_is_mutable(
                    bank_account_id=current.bank_account_id,
                    period_start=period_start,
                    period_end=period_end,
                )

                self._assert_no_duplicate_lines(
                    bank_account_id=current.bank_account_id,
                    parsed_rows=parsed_rows,
                )

                current.file_hash = file_hash
                current.file_dedupe_key = (
                    BankStatementImport.build_file_dedupe_key(
                        bank_account_id=current.bank_account_id,
                        file_hash=file_hash,
                    )
                )

                if not current.file_name and current.source_file:
                    current.file_name = Path(
                        current.source_file.name
                    ).name

                if not current.period_start:
                    current.period_start = period_start

                if not current.period_end:
                    current.period_end = period_end

                current.status = BankStatementImport.STATUS_PROCESSING
                current.processed_at = None
                current.error_message = ""

                current.save(
                    update_fields=[
                        "file_hash",
                        "file_dedupe_key",
                        "file_name",
                        "period_start",
                        "period_end",
                        "status",
                        "processed_at",
                        "error_message",
                    ]
                )

                started_processing = True

                lines = [
                    BankStatementLine(
                        statement_import=current,
                        bank_account_id=current.bank_account_id,
                        transaction_date=row["transaction_date"],
                        posted_date=row["posted_date"],
                        description=row["description"],
                        reference=row["reference"],
                        amount=row["amount"],
                        balance_after=row["balance_after"],
                        external_id=row["external_id"],
                        external_dedupe_key=(
                            BankStatementLine.build_external_dedupe_key(
                                bank_account_id=current.bank_account_id,
                                external_id=row["external_id"],
                            )
                        ),
                        fingerprint=row["fingerprint"],
                    )
                    for row in parsed_rows
                ]

                BankStatementLine.objects.bulk_create(lines)

                current.status = BankStatementImport.STATUS_PROCESSED
                current.processed_at = timezone.now()
                current.error_message = ""

                current.save(
                    update_fields=[
                        "status",
                        "processed_at",
                        "error_message",
                    ]
                )

                return len(lines)

        except IntegrityError as exc:
            if started_processing:
                self._mark_failed(
                    statement_import_id=statement_import.pk,
                    message="Duplicate bank import data detected.",
                )

            raise BankImportError(
                "Duplicate bank import data detected."
            ) from exc

        except BankImportError as exc:
            if started_processing:
                self._mark_failed(
                    statement_import_id=statement_import.pk,
                    message=str(exc),
                )

            raise

        except Exception as exc:
            if started_processing:
                self._mark_failed(
                    statement_import_id=statement_import.pk,
                    message=str(exc),
                )

            raise BankImportError(
                f"Bank import failed: {exc}"
            ) from exc

    def _read_source_bytes(
        self,
        statement_import: BankStatementImport,
    ) -> bytes:
        statement_import.source_file.open("rb")

        try:
            raw_bytes = statement_import.source_file.read()
        finally:
            statement_import.source_file.close()

        if not raw_bytes:
            raise BankImportError("The bank statement file is empty.")

        return raw_bytes

    def _parse_csv(
        self,
        raw_bytes: bytes,
    ) -> list[dict]:
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise BankImportError(
                "CSV file must use UTF-8 encoding."
            ) from exc

        reader = csv.DictReader(StringIO(text))

        if not reader.fieldnames:
            raise BankImportError("CSV header row is missing.")

        normalized_headers = {
            header.strip().lower()
            for header in reader.fieldnames
            if header
        }

        missing = self.REQUIRED_COLUMNS - normalized_headers

        if missing:
            raise BankImportError(
                "Missing required columns: "
                + ", ".join(sorted(missing))
            )

        parsed_rows: list[dict] = []

        for row_number, raw_row in enumerate(reader, start=2):
            row = {
                (key or "").strip().lower():
                    (value or "").strip()
                for key, value in raw_row.items()
                if key is not None
            }

            if not any(row.values()):
                continue

            description = row.get("description", "").strip()

            if not description:
                raise BankImportError(
                    f"Row {row_number}: description is required."
                )

            transaction_date = self._parse_date(
                row.get("transaction_date"),
                row_number=row_number,
                field_name="transaction_date",
                required=True,
            )

            posted_date = self._parse_date(
                row.get("posted_date"),
                row_number=row_number,
                field_name="posted_date",
                required=False,
            )

            amount = self._parse_money(
                row.get("amount"),
                row_number=row_number,
                field_name="amount",
                required=True,
            )

            balance_after = self._parse_money(
                row.get("balance_after"),
                row_number=row_number,
                field_name="balance_after",
                required=False,
            )

            reference = row.get("reference", "").strip()
            external_id = row.get("external_id", "").strip()

            fingerprint = self._build_fingerprint(
                transaction_date=transaction_date,
                posted_date=posted_date,
                description=description,
                reference=reference,
                amount=amount,
                balance_after=balance_after,
            )

            parsed_rows.append(
                {
                    "transaction_date": transaction_date,
                    "posted_date": posted_date,
                    "description": description,
                    "reference": reference,
                    "amount": amount,
                    "balance_after": balance_after,
                    "external_id": external_id,
                    "fingerprint": fingerprint,
                }
            )

        return parsed_rows

    def _validate_import_state(
        self,
        statement_import: BankStatementImport,
    ):
        if statement_import.status == BankStatementImport.STATUS_PROCESSING:
            raise BankImportError(
                "This bank statement import is already processing."
            )

        if statement_import.status == BankStatementImport.STATUS_PROCESSED:
            raise BankImportError(
                "This bank statement import has already been processed."
            )

        if statement_import.status == BankStatementImport.STATUS_ARCHIVED:
            raise BankImportError(
                "Archived bank statement imports cannot be processed."
            )

    def _assert_period_is_mutable(
        self,
        *,
        bank_account_id: int,
        period_start: date,
        period_end: date,
    ):
        protected_exists = (
            BankReconciliationSession.objects
            .filter(
                bank_account_id=bank_account_id,
                status__in=[
                    BankReconciliationSession.STATUS_COMPLETED,
                    BankReconciliationSession.STATUS_LOCKED,
                ],
                period_start__lte=period_end,
                period_end__gte=period_start,
            )
            .exists()
        )

        if protected_exists:
            raise BankImportError(
                "Bank transactions cannot be imported into a "
                "completed or locked reconciliation period."
            )

    def _assert_no_duplicate_lines(
        self,
        *,
        bank_account_id: int,
        parsed_rows: list[dict],
    ):
        external_ids = [
            row["external_id"]
            for row in parsed_rows
            if row["external_id"]
        ]

        if len(external_ids) != len(set(external_ids)):
            raise BankImportError(
                "Duplicate external transaction IDs exist inside the CSV file."
            )

        if external_ids:
            existing_external_id = (
                BankStatementLine.objects
                .filter(
                    bank_account_id=bank_account_id,
                    external_id__in=external_ids,
                )
                .exists()
            )

            if existing_external_id:
                raise BankImportError(
                    "One or more bank transactions have already been imported."
                )

        protected_fingerprints = [
            row["fingerprint"]
            for row in parsed_rows
            if row["balance_after"] is not None
        ]

        if len(protected_fingerprints) != len(
            set(protected_fingerprints)
        ):
            raise BankImportError(
                "Duplicate bank transaction fingerprints exist inside the CSV file."
            )

        if protected_fingerprints:
            existing_fingerprint = (
                BankStatementLine.objects
                .filter(
                    bank_account_id=bank_account_id,
                    fingerprint__in=protected_fingerprints,
                )
                .exists()
            )

            if existing_fingerprint:
                raise BankImportError(
                    "One or more bank transactions appear to have already been imported."
                )

    def _parse_date(
        self,
        value: str | None,
        *,
        row_number: int,
        field_name: str,
        required: bool,
    ) -> date | None:
        value = (value or "").strip()

        if not value:
            if required:
                raise BankImportError(
                    f"Row {row_number}: {field_name} is required."
                )

            return None

        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise BankImportError(
                f"Row {row_number}: invalid {field_name} '{value}'. "
                "Expected YYYY-MM-DD."
            ) from exc

    def _parse_money(
        self,
        value: str | None,
        *,
        row_number: int,
        field_name: str,
        required: bool,
    ) -> Decimal | None:
        value = (value or "").strip()

        if not value:
            if required:
                raise BankImportError(
                    f"Row {row_number}: {field_name} is required."
                )

            return None

        negative = value.startswith("(") and value.endswith(")")

        normalized = value.strip("()").strip()
        normalized = normalized.upper().replace("CAD", "")
        normalized = normalized.replace("$", "")
        normalized = normalized.replace(",", "")
        normalized = normalized.strip()

        try:
            amount = Decimal(normalized)
        except InvalidOperation as exc:
            raise BankImportError(
                f"Row {row_number}: invalid {field_name} '{value}'."
            ) from exc

        if negative:
            amount = -abs(amount)

        return amount.quantize(MONEY_QUANT)

    def _build_fingerprint(
        self,
        *,
        transaction_date: date,
        posted_date: date | None,
        description: str,
        reference: str,
        amount: Decimal,
        balance_after: Decimal | None,
    ) -> str:
        payload = json.dumps(
            [
                transaction_date.isoformat(),
                posted_date.isoformat() if posted_date else "",
                description.strip(),
                reference.strip(),
                f"{amount:.2f}",
                f"{balance_after:.2f}" if balance_after is not None else "",
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def _mark_failed(
        self,
        *,
        statement_import_id: int,
        message: str,
    ):
        BankStatementImport.objects.filter(
            pk=statement_import_id
        ).update(
            status=BankStatementImport.STATUS_FAILED,
            error_message=(message or "")[:4000],
            processed_at=None,
        )