# apps/accounting/seeds/chart_of_accounts.py

from apps.accounting.models import Account, AccountCategory
from apps.accounting.config.chart_of_accounts import CHART_OF_ACCOUNTS


CATEGORY_CONFIG = [
    {
        "name": "Assets",
        "code_prefix": "1",
        "sort_order": 1,
        "description": "Asset accounts",
    },
    {
        "name": "Liabilities",
        "code_prefix": "2",
        "sort_order": 2,
        "description": "Liability accounts",
    },
    {
        "name": "Equity",
        "code_prefix": "3",
        "sort_order": 3,
        "description": "Equity accounts",
    },
    {
        "name": "Revenue",
        "code_prefix": "4",
        "sort_order": 4,
        "description": "Revenue accounts",
    },
    {
        "name": "Expenses",
        "code_prefix": "5",
        "sort_order": 5,
        "description": "Expense accounts",
    },
]


def seed_chart_of_accounts():
    """
    Create or update the default Chart of Accounts.
    Safe to run multiple times.
    """

    created_categories = {}

    for item in CATEGORY_CONFIG:
        category, _ = AccountCategory.objects.update_or_create(
            name=item["name"],
            defaults={
                "code_prefix": item["code_prefix"],
                "description": item["description"],
                "sort_order": item["sort_order"],
                "is_active": True,
            },
        )
        created_categories[item["name"]] = category

    # First pass: create/update accounts without parent
    for item in CHART_OF_ACCOUNTS:
        Account.objects.update_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "account_type": item["account_type"],
                "category": created_categories[item["category"]],
                "normal_balance": item["normal_balance"],
                "allows_posting": item["allows_posting"],
                "is_system": item["is_system"],
                "description": item["description"],
                "is_active": True,
                "sort_order": item["sort_order"],
            },
        )

    # Second pass: assign parent after all accounts exist
    for item in CHART_OF_ACCOUNTS:
        if not item["parent_code"]:
            continue

        account = Account.objects.get(code=item["code"])
        parent = Account.objects.get(code=item["parent_code"])

        if account.parent_id != parent.id:
            account.parent = parent
            account.save(update_fields=["parent", "updated_at"])