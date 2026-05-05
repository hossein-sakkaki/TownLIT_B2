# apps/accounts/utils/country.py

from apps.profilesOrg.constants import COUNTRY_CHOICES


COUNTRY_CODE_SET = {code.upper() for code, _ in COUNTRY_CHOICES}
COUNTRY_NAME_TO_CODE = {
    str(name).strip().lower(): str(code).upper()
    for code, name in COUNTRY_CHOICES
}


def normalize_profile_country(value):
    """
    Normalize a country value for CustomUser.country.

    Accepts:
    - ISO-like 2-letter codes: "CA", "ca"
    - country names from COUNTRY_CHOICES: "Canada", "canada"

    Returns:
    - valid 2-letter country code
    - None if invalid/unknown

    This is a profile preference hint, not verified identity data.
    """
    if not value:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    upper = raw.upper()

    if len(upper) == 2 and upper in COUNTRY_CODE_SET:
        return upper

    return COUNTRY_NAME_TO_CODE.get(raw.lower())