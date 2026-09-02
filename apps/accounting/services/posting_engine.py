# apps/accounting/services/posting_engine.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.accounting.models import (
    Account,
    Budget,
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
from .fund_policy_service import (
    validate_fund_budget_limit,
    validate_fund_posting_policy,
)
from .fund_service import validate_fund_budget_match
from .period_service import assert_can_post_to_date
from .schemas import JournalEntryInput, JournalLineInput


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class PostingEngine:
    """Central accounting posting engine."""

    def post(self, payload: JournalEntryInput) -> JournalEntry:
        """Validate and persist one posted journal entry."""

        self._validate_payload(payload)
        assert_can_post_to_date(payload.entry_date)

        with db_transaction.atomic():
            self._ensure_not_duplicate(payload)

            account_map = self._resolve_accounts(payload.lines)
            fund_map = self._resolve_funds(payload.lines)

            prepared_lines = self._prepare_lines(
                payload=payload,
                account_map=account_map,
                fund_map=fund_map,
            )

            self._validate_budget_totals(prepared_lines)

            entry = self._create_posted_entry(payload)

            Transaction.objects.bulk_create(
                [
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
            )

            from .workflow_service import mark_posted

            mark_posted(journal_entry=entry)

            return entry

    def post_draft(
        self,
        *,
        journal_entry: JournalEntry,
        approved_by=None,
    ) -> JournalEntry:
        """Post an existing draft through the same validation pipeline."""

        with db_transaction.atomic():
            entry = (
                JournalEntry.objects.select_for_update()
                .select_related("created_by", "approved_by")
                .get(pk=journal_entry.pk)
            )

            if entry.status != JournalEntry.STATUS_DRAFT:
                raise JournalEntryValidationError(
                    "Only draft journal entries can be posted."
                )

            transactions = list(
                Transaction.objects.select_for_update()
                .select_related(
                    "account",
                    "fund",
                    "budget_line",
                    "budget_line__budget",
                )
                .filter(journal_entry=entry)
                .order_by("line_number", "id")
            )

            payload = JournalEntryInput(
                entry_date=entry.entry_date,
                description=entry.description,
                reference=entry.reference,
                source_app=entry.source_app,
                source_model=entry.source_model,
                source_ref=entry.source_ref,
                internal_note=entry.internal_note,
                currency=entry.currency,
                created_by=entry.created_by,
                approved_by=approved_by or entry.approved_by,
                lines=[
                    JournalLineInput(
                        account_code=tx.account.code,
                        debit=tx.debit,
                        credit=tx.credit,
                        memo=tx.memo,
                        line_number=tx.line_number,
                        fund_code=tx.fund.code if tx.fund else None,
                        budget_line_id=tx.budget_line_id,
                    )
                    for tx in transactions
                ],
            )

            self._validate_payload(payload)
            assert_can_post_to_date(payload.entry_date)
            self._ensure_not_duplicate(payload)

            account_map = self._resolve_accounts(payload.lines)
            fund_map = self._resolve_funds(payload.lines)

            prepared_lines = self._prepare_lines(
                payload=payload,
                account_map=account_map,
                fund_map=fund_map,
            )

            self._validate_budget_totals(prepared_lines)

            approved_user = approved_by or entry.approved_by
            posted_at = timezone.now()

            updated = JournalEntry.objects.filter(
                pk=entry.pk,
                status=JournalEntry.STATUS_DRAFT,
            ).update(
                status=JournalEntry.STATUS_POSTED,
                posted_at=posted_at,
                approved_by=approved_user,
                updated_at=posted_at,
            )

            if updated != 1:
                raise JournalEntryValidationError(
                    "Journal entry posting state changed concurrently."
                )

            entry.refresh_from_db()

            from .workflow_service import mark_posted

            mark_posted(journal_entry=entry)

            return entry

    def _create_posted_entry(
        self,
        payload: JournalEntryInput,
    ) -> JournalEntry:
        """Create a posted entry through the trusted core path."""

        entry = JournalEntry(
            entry_number=generate_entry_number(),
            entry_date=payload.entry_date,
            description=payload.description.strip(),
            reference=payload.reference.strip(),
            source_app=payload.source_app.strip(),
            source_model=payload.source_model.strip(),
            source_ref=payload.source_ref.strip(),
            internal_note=payload.internal_note,
            currency=payload.currency.strip().upper() or "CAD",
            status=JournalEntry.STATUS_POSTED,
            posted_at=timezone.now(),
            created_by=payload.created_by,
            approved_by=payload.approved_by,
        )

        entry._allow_posted_create = True
        entry.save(force_insert=True)

        return entry

    def _prepare_lines(
        self,
        *,
        payload: JournalEntryInput,
        account_map: dict[str, Account],
        fund_map: dict[str, Fund],
    ) -> list[dict]:
        """Resolve dimensions and prepare transaction lines."""

        prepared_lines: list[dict] = []

        for index, line in enumerate(payload.lines, start=1):
            account_code = line.account_code.strip()
            fund_code = (line.fund_code or "").strip()

            account = account_map[account_code]
            fund = fund_map.get(fund_code)

            budget_line = self._resolve_budget_line(
                line=line,
                fund=fund,
            )

            # A funded budget can infer its fund.
            if not fund and budget_line and budget_line.budget.fund_id:
                fund = budget_line.budget.fund
                fund_code = fund.code

            debit = self._normalize_amount(line.debit)
            credit = self._normalize_amount(line.credit)

            validate_fund_budget_match(
                fund,
                budget_line,
            )

            validate_fund_posting_policy(
                fund=fund,
                account=account,
                budget_line=budget_line,
                entry_date=payload.entry_date,
                debit=debit,
                credit=credit,
                check_budget_limit=False,
            )

            prepared_lines.append(
                {
                    "line_number": line.line_number or index,
                    "account": account,
                    "debit": debit,
                    "credit": credit,
                    "memo": line.memo,
                    "fund": fund,
                    "budget_line": budget_line,
                    "fund_code": fund.code if fund else "",
                    "budget_code": budget_line.code if budget_line else "",
                }
            )

        return prepared_lines

    def _resolve_budget_line(
        self,
        *,
        line: JournalLineInput,
        fund: Fund | None,
    ) -> BudgetLine | None:
        """Resolve a budget line without global-code ambiguity."""

        legacy_code = (line.budget_code or "").strip()
        line_code = (line.budget_line_code or "").strip()
        plan_code = (line.budget_plan_code or "").strip()
        line_id = line.budget_line_id

        if legacy_code and line_code and legacy_code != line_code:
            raise JournalEntryValidationError(
                "budget_code and budget_line_code refer to different values."
            )

        effective_line_code = line_code or legacy_code

        if not line_id and not effective_line_code:
            if plan_code:
                raise JournalEntryValidationError(
                    "budget_plan_code requires budget_line_code or budget_line_id."
                )
            return None

        qs = (
            BudgetLine.objects.select_for_update()
            .select_related("budget", "budget__fund")
            .filter(
                is_active=True,
                budget__is_active=True,
                budget__status=Budget.STATUS_ACTIVE,
            )
        )

        if line_id:
            qs = qs.filter(pk=line_id)

        if effective_line_code:
            qs = qs.filter(code=effective_line_code)

        if plan_code:
            qs = qs.filter(budget__code=plan_code)

        if fund:
            qs = qs.filter(budget__fund=fund)

        matches = list(qs.order_by("id")[:2])

        if not matches:
            label = (
                f"id={line_id}"
                if line_id
                else f"code='{effective_line_code}'"
            )
            raise JournalEntryValidationError(
                f"Budget line not found or inactive: {label}."
            )

        if len(matches) > 1:
            raise JournalEntryValidationError(
                f"Budget line code '{effective_line_code}' is ambiguous. "
                "Provide budget_plan_code or budget_line_id."
            )

        return matches[0]

    def _validate_budget_totals(
        self,
        prepared_lines: list[dict],
    ) -> None:
        """Validate aggregated budget usage once per budget line."""

        grouped = defaultdict(
            lambda: {
                "fund": None,
                "budget_line": None,
                "amount": ZERO,
            }
        )

        for item in prepared_lines:
            account = item["account"]
            fund = item["fund"]
            budget_line = item["budget_line"]

            if account.account_type != Account.TYPE_EXPENSE:
                continue

            if not fund or not budget_line:
                continue

            key = (fund.id, budget_line.id)

            grouped[key]["fund"] = fund
            grouped[key]["budget_line"] = budget_line
            grouped[key]["amount"] += item["debit"] - item["credit"]

        for item in grouped.values():
            validate_fund_budget_limit(
                fund=item["fund"],
                budget_line=item["budget_line"],
                posting_amount=item["amount"],
            )

    def _validate_payload(
        self,
        payload: JournalEntryInput,
    ) -> None:
        """Validate the complete journal payload."""

        if not payload.entry_date:
            raise JournalEntryValidationError(
                "Entry date is required."
            )

        if not payload.description or not payload.description.strip():
            raise JournalEntryValidationError(
                "Description is required."
            )

        if not payload.lines:
            raise JournalEntryValidationError(
                "At least one journal line is required."
            )

        total_debit = ZERO
        total_credit = ZERO
        seen_line_numbers: set[int] = set()

        for index, line in enumerate(payload.lines, start=1):
            effective_line_number = line.line_number or index

            self._validate_line(
                line=line,
                index=index,
                effective_line_number=effective_line_number,
            )

            if effective_line_number in seen_line_numbers:
                raise JournalEntryValidationError(
                    f"Duplicate line_number detected: {effective_line_number}"
                )

            seen_line_numbers.add(effective_line_number)

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

    def _validate_line(
        self,
        *,
        line: JournalLineInput,
        index: int,
        effective_line_number: int,
    ) -> None:
        """Validate one journal line."""

        if not line.account_code or not line.account_code.strip():
            raise JournalEntryValidationError(
                f"Line {index}: account_code is required."
            )

        if effective_line_number <= 0:
            raise JournalEntryValidationError(
                f"Line {index}: line_number must be greater than zero."
            )

        if line.budget_line_id is not None and line.budget_line_id <= 0:
            raise JournalEntryValidationError(
                f"Line {index}: budget_line_id must be greater than zero."
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

    def _resolve_accounts(
        self,
        lines: Iterable[JournalLineInput],
    ) -> dict[str, Account]:
        """Resolve all posting accounts."""

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

        account_map = {
            account.code: account
            for account in accounts
        }

        missing_codes = [
            code
            for code in codes
            if code not in account_map
        ]

        if missing_codes:
            raise AccountNotFoundError(
                f"Accounts not found or inactive: {', '.join(missing_codes)}"
            )

        non_postable = sorted(
            account.code
            for account in accounts
            if not account.allows_posting
        )

        if non_postable:
            raise JournalEntryValidationError(
                f"Posting is not allowed to group accounts: "
                f"{', '.join(non_postable)}"
            )

        return account_map

    def _resolve_funds(
        self,
        lines: Iterable[JournalLineInput],
    ) -> dict[str, Fund]:
        """Resolve explicit fund codes."""

        fund_codes = sorted(
            {
                (line.fund_code or "").strip()
                for line in lines
                if (line.fund_code or "").strip()
            }
        )

        if not fund_codes:
            return {}

        funds = (
            Fund.objects.filter(
                code__in=fund_codes,
                is_active=True,
            )
            .select_related("policy")
        )

        fund_map = {
            fund.code: fund
            for fund in funds
        }

        missing_codes = [
            code
            for code in fund_codes
            if code not in fund_map
        ]

        if missing_codes:
            raise JournalEntryValidationError(
                f"Funds not found or inactive: {', '.join(missing_codes)}"
            )

        return fund_map

    def _ensure_not_duplicate(
        self,
        payload: JournalEntryInput,
    ) -> None:
        """Prevent duplicate source postings."""

        if not (
            payload.source_app
            and payload.source_model
            and payload.source_ref
        ):
            return

        exists = JournalEntry.objects.filter(
            source_app=payload.source_app.strip(),
            source_model=payload.source_model.strip(),
            source_ref=payload.source_ref.strip(),
            status=JournalEntry.STATUS_POSTED,
        ).exists()

        if exists:
            raise JournalEntryValidationError(
                "A posted journal entry already exists for this source reference."
            )

    def _normalize_amount(
        self,
        value: Decimal | None,
    ) -> Decimal:
        """Normalize money to cents."""

        if value is None:
            return ZERO

        return Decimal(str(value)).quantize(CENT)


def post_journal_entry(
    payload: JournalEntryInput,
) -> JournalEntry:
    """Post one journal entry."""

    return PostingEngine().post(payload)