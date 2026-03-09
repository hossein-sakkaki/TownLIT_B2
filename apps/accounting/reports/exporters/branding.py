# apps/accounting/reports/exporters/branding.py

from pathlib import Path
from django.conf import settings


TOWNLIT_BRAND = {
    "company_name": "TownLIT",
    "report_footer_note": "Confidential financial report for internal use unless otherwise approved.",
    "currency": "CAD",
}


def get_static_logo_path(filename: str) -> str:
    """
    Return absolute path for a logo inside static/logo.
    """

    base_dir = Path(settings.BASE_DIR)
    return str(base_dir / "static" / "logo" / filename)