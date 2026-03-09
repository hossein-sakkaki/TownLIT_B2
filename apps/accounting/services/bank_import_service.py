# apps/accounting/services/bank_import_service.py

import csv
from decimal import Decimal
from io import TextIOWrapper

from apps.accounting.models import BankStatementImport, BankStatementLine


class BankImportError(Exception):
    """Raised when bank import fails."""
    pass


class CSVBankImportService:
    """
    Import bank statement lines from CSV.
    Expected columns:
    transaction_date, posted_date, description, reference, amount, balance_after, external_id
    """

    REQUIRED_COLUMNS = {"transaction_date", "description", "amount"}

    def import_csv(self, *, statement_import: BankStatementImport):
        """
        Parse CSV file and create statement lines.
        """

        if not statement_import.source_file:
            raise BankImportError("No source file attached.")

        statement_import.source_file.open("rb")
        wrapper = TextIOWrapper(statement_import.source_file.file, encoding="utf-8-sig")
        reader = csv.DictReader(wrapper)

        headers = set(reader.fieldnames or [])
        missing = self.REQUIRED_COLUMNS - headers
        if missing:
            raise BankImportError(f"Missing required columns: {', '.join(sorted(missing))}")

        created = 0

        for row in reader:
            BankStatementLine.objects.create(
                statement_import=statement_import,
                bank_account=statement_import.bank_account,
                transaction_date=row["transaction_date"],
                posted_date=row.get("posted_date") or None,
                description=(row.get("description") or "").strip(),
                reference=(row.get("reference") or "").strip(),
                amount=Decimal(str(row["amount"])),
                balance_after=Decimal(str(row["balance_after"])) if row.get("balance_after") else None,
                external_id=(row.get("external_id") or "").strip(),
            )
            created += 1

        statement_import.status = BankStatementImport.STATUS_PROCESSED
        statement_import.save(update_fields=["status"])

        return created