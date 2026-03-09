# apps/accounting/services/recurring_service.py

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from apps.accounting.models import RecurringJournalTemplate
from apps.accounting.services.templates.founder import record_home_office_allocation
from apps.accounting.services.templates.founder import record_founder_loan
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput


class RecurringTemplateError(Exception):
    """Raised when recurring template execution fails."""
    pass


def run_recurring_template(*, template: RecurringJournalTemplate, run_date, created_by=None, approved_by=None):
    """
    Execute one recurring template and return the created journal entry.
    """

    if template.status != RecurringJournalTemplate.STATUS_ACTIVE or not template.is_active:
        raise RecurringTemplateError("Template is not active.")

    config = template.config or {}
    template_type = template.template_type

    if template_type == RecurringJournalTemplate.TEMPLATE_HOME_OFFICE:
        entry = record_home_office_allocation(
            entry_date=run_date,
            total_paid=config["total_paid"],
            business_share=config["business_share"],
            personal_share=config["personal_share"],
            description=config.get("description", template.name),
            reference=config.get("reference", ""),
            source_ref=f"{template.code}-{run_date.isoformat()}",
            created_by=created_by,
            approved_by=approved_by,
        )
    elif template_type == RecurringJournalTemplate.TEMPLATE_FOUNDER_LOAN:
        entry = record_founder_loan(
            entry_date=run_date,
            amount=config["amount"],
            expense_account_code=config["expense_account_code"],
            description=config.get("description", template.name),
            reference=config.get("reference", ""),
            source_ref=f"{template.code}-{run_date.isoformat()}",
            created_by=created_by,
            approved_by=approved_by,
        )
    else:
        lines = [
            JournalLineInput(
                account_code=line["account_code"],
                debit=line.get("debit", 0),
                credit=line.get("credit", 0),
                memo=line.get("memo", ""),
                line_number=line.get("line_number", index + 1),
                fund_code=line.get("fund_code"),
                budget_code=line.get("budget_code"),
            )
            for index, line in enumerate(config.get("lines", []))
        ]

        entry = post_journal_entry(
            JournalEntryInput(
                entry_date=run_date,
                description=config.get("description", template.name),
                reference=config.get("reference", ""),
                source_app="accounting",
                source_model="recurring_template",
                source_ref=f"{template.code}-{run_date.isoformat()}",
                lines=lines,
                created_by=created_by,
                approved_by=approved_by,
            )
        )

    template.last_run_date = run_date
    template.next_run_date = _calculate_next_run_date(
        run_date=run_date,
        frequency=template.frequency,
    )
    template.save(update_fields=["last_run_date", "next_run_date", "updated_at"])

    return entry


def _calculate_next_run_date(*, run_date, frequency: str):
    """
    Calculate next recurring run date.
    """

    if frequency == RecurringJournalTemplate.FREQ_MONTHLY:
        return run_date + relativedelta(months=1)

    if frequency == RecurringJournalTemplate.FREQ_QUARTERLY:
        return run_date + relativedelta(months=3)

    if frequency == RecurringJournalTemplate.FREQ_YEARLY:
        return run_date + relativedelta(years=1)

    return run_date + timedelta(days=30)