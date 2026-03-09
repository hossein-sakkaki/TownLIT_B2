# apps/accounting/reports/exporters/base.py

def build_period_label(date_from=None, date_to=None) -> str:
    """
    Build readable period label.
    """

    if date_from and date_to:
        return f"{date_from} to {date_to}"
    if date_from:
        return f"From {date_from}"
    if date_to:
        return f"Up to {date_to}"
    return "All periods"