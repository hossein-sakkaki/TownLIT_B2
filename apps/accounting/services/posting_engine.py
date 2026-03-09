# apps/accounting/services/posting_engine.py

from decimal import Decimal
from typing import Iterable

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.accounting.models import (
    Account,
    BudgetLine,
    Fund,
    JournalEntry,
    Transaction,
)
from .entry_number import generate_entry_number
from .exceptions import (
    AccountNotFoundError,
    JournalEntryValidationError,
)
from .fund_policy_service import validate_fund_posting_policy
from .fund_service import validate_fund_budget_match
from .schemas import JournalEntryInput, JournalLineInput
from .period_service import assert_can_post_to_date


ZERO = Decimal("0.00")


class PostingEngine:
    """
    Central service for posting journal entries.
    """

    def post(self, payload: JournalEntryInput) -> JournalEntry:
        """
        Validate and persist a posted journal entry.
        """

        self._ensure_not_duplicate(payload)
        self._validate_payload(payload)
        assert_can_post_to_date(payload.entry_date)

        account_map = self._resolve_accounts(payload.lines)
        fund_map = self._resolve_funds(payload.lines)
        budget_line_map = self._resolve_budget_lines(payload.lines)

        prepared_lines = self._prepare_lines(
            payload=payload,
            account_map=account_map,
            fund_map=fund_map,
            budget_line_map=budget_line_map,
        )

        with db_transaction.atomic():
            entry = JournalEntry.objects.create(
                entry_number=generate_entry_number(),
                entry_date=payload.entry_date,
                description=payload.description,
                reference=payload.reference,
                source_app=payload.source_app,
                source_model=payload.source_model,
                source_ref=payload.source_ref,
                internal_note=payload.internal_note,
                currency=payload.currency,
                status=JournalEntry.STATUS_POSTED,
                posted_at=timezone.now(),
                created_by=payload.created_by,
                approved_by=payload.approved_by,
            )

            transactions = [
                Transaction(
                    journal_entry=entry,
                    line_number=item["line_number"],
                    account=item["account"],
                    debit=item["debit"],
                    credit=item["credit"],
                    memo=item["memo"],
                    fund=item["fund"],
                    budget_line=item["budget_line"],
                    fund_code=item["fund_code"],
                    budget_code=item["budget_code"],
                )
                for item in prepared_lines
            ]

            Transaction.objects.bulk_create(transactions)

            return entry

    def _prepare_lines(
        self,
        *,
        payload: JournalEntryInput,
        account_map: dict[str, Account],
        fund_map: dict[str, Fund],
        budget_line_map: dict[str, BudgetLine],
    ) -> list[dict]:
        """
        Prepare validated transaction line payloads.
        """

        prepared_lines: list[dict] = []

        for idx, line in enumerate(payload.lines, start=1):
            account_code = line.account_code.strip()
            fund_code = (line.fund_code or "").strip()
            budget_code = (line.budget_code or "").strip()

            account = account_map[account_code]
            fund = fund_map.get(fund_code)
            budget_line = budget_line_map.get(budget_code)

            debit = self._normalize_amount(line.debit)
            credit = self._normalize_amount(line.credit)

            validate_fund_budget_match(fund, budget_line)

            validate_fund_posting_policy(
                fund=fund,
                account=account,
                budget_line=budget_line,
                entry_date=payload.entry_date,
                debit=debit,
                credit=credit,
            )

            prepared_lines.append(
                {
                    "line_number": line.line_number or idx,
                    "account": account,
                    "debit": debit,
                    "credit": credit,
                    "memo": line.memo,
                    "fund": fund,
                    "budget_line": budget_line,
                    "fund_code": fund.code if fund else fund_code,
                    "budget_code": budget_line.code if budget_line else budget_code,
                }
            )

        return prepared_lines

    def _validate_payload(self, payload: JournalEntryInput) -> None:
        """
        Validate the journal entry before saving.
        """

        if not payload.entry_date:
            raise JournalEntryValidationError("Entry date is required.")

        if not payload.description or not payload.description.strip():
            raise JournalEntryValidationError("Description is required.")

        if not payload.lines:
            raise JournalEntryValidationError(
                "At least one journal line is required."
            )

        total_debit = ZERO
        total_credit = ZERO
        seen_line_numbers: set[int] = set()

        for index, line in enumerate(payload.lines, start=1):
            self._validate_line(line, index)

            if line.line_number in seen_line_numbers:
                raise JournalEntryValidationError(
                    f"Duplicate line_number detected: {line.line_number}"
                )
            seen_line_numbers.add(line.line_number)

            total_debit += self._normalize_amount(line.debit)
            total_credit += self._normalize_amount(line.credit)

        if total_debit != total_credit:
            raise JournalEntryValidationError(
                f"Debits and credits must balance. "
                f"Debit={total_debit}, Credit={total_credit}"
            )

        if total_debit <= ZERO:
            raise JournalEntryValidationError(
                "Total debit must be greater than zero."
            )

    def _validate_line(self, line: JournalLineInput, index: int) -> None:
        """
        Validate one journal line.
        """

        if not line.account_code or not line.account_code.strip():
            raise JournalEntryValidationError(
                f"Line {index}: account_code is required."
            )

        debit = self._normalize_amount(line.debit)
        credit = self._normalize_amount(line.credit)

        if debit < ZERO or credit < ZERO:
            raise JournalEntryValidationError(
                f"Line {index}: debit/credit cannot be negative."
            )

        if debit == ZERO and credit == ZERO:
            raise JournalEntryValidationError(
                f"Line {index}: either debit or credit is required."
            )

        if debit > ZERO and credit > ZERO:
            raise JournalEntryValidationError(
                f"Line {index}: a line cannot have both debit and credit."
            )

        if line.line_number <= 0:
            raise JournalEntryValidationError(
                f"Line {index}: line_number must be greater than zero."
            )

    def _resolve_accounts(self, lines: Iterable[JournalLineInput]) -> dict[str, Account]:
        """
        Resolve all account codes in one query.
        """

        codes = sorted(
            {
                line.account_code.strip()
                for line in lines
                if line.account_code and line.account_code.strip()
            }
        )

        accounts = Account.objects.filter(
            code__in=codes,
            is_active=True,
        )

        account_map = {account.code: account for account in accounts}

        missing_codes = [code for code in codes if code not in account_map]
        if missing_codes:
            raise AccountNotFoundError(
                f"Accounts not found or inactive: {', '.join(missing_codes)}"
            )

        non_postable = [
            account.code
            for account in accounts
            if not account.allows_posting
        ]
        if non_postable:
            raise JournalEntryValidationError(
                f"Posting is not allowed to group accounts: {', '.join(sorted(non_postable))}"
            )

        return account_map

    def _resolve_funds(self, lines: Iterable[JournalLineInput]) -> dict[str, Fund]:
        """
        Resolve all fund codes in one query.
        """

        fund_codes = sorted(
            {
                (line.fund_code or "").strip()
                for line in lines
                if (line.fund_code or "").strip()
            }
        )

        if not fund_codes:
            return {}

        funds = Fund.objects.filter(
            code__in=fund_codes,
            is_active=True,
        ).select_related("policy")

        fund_map = {fund.code: fund for fund in funds}

        missing_codes = [code for code in fund_codes if code not in fund_map]
        if missing_codes:
            raise JournalEntryValidationError(
                f"Funds not found or inactive: {', '.join(missing_codes)}"
            )

        return fund_map

    def _resolve_budget_lines(self, lines: Iterable[JournalLineInput]) -> dict[str, BudgetLine]:
        """
        Resolve all budget codes in one query.
        """

        budget_codes = sorted(
            {
                (line.budget_code or "").strip()
                for line in lines
                if (line.budget_code or "").strip()
            }
        )

        if not budget_codes:
            return {}

        budget_lines = BudgetLine.objects.filter(
            code__in=budget_codes,
            is_active=True,
            budget__is_active=True,
        ).select_related("budget", "budget__fund")

        budget_line_map = {line.code: line for line in budget_lines}

        missing_codes = [code for code in budget_codes if code not in budget_line_map]
        if missing_codes:
            raise JournalEntryValidationError(
                f"Budget lines not found or inactive: {', '.join(missing_codes)}"
            )

        return budget_line_map

    def _ensure_not_duplicate(self, payload: JournalEntryInput) -> None:
        """
        Prevent duplicate posting for the same source reference.
        """

        if not (
            payload.source_app
            and payload.source_model
            and payload.source_ref
        ):
            return

        exists = JournalEntry.objects.filter(
            source_app=payload.source_app,
            source_model=payload.source_model,
            source_ref=payload.source_ref,
            status=JournalEntry.STATUS_POSTED,
        ).exists()

        if exists:
            raise JournalEntryValidationError(
                "A posted journal entry already exists for this source reference."
            )

    def _normalize_amount(self, value: Decimal | None) -> Decimal:
        """
        Normalize to two decimal places.
        """

        if value is None:
            return ZERO

        return Decimal(value).quantize(Decimal("0.01"))


def post_journal_entry(payload: JournalEntryInput) -> JournalEntry:
    """
    Convenience wrapper around PostingEngine.
    """

    return PostingEngine().post(payload)