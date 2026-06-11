# validators/usernameValidators/username_normalizer.py

import re


def normalize_username(value: str | None) -> str:
    """
    Normalize username before validation/storage.
    """
    if value is None:
        return ""

    username = str(value).strip().lower()
    username = re.sub(r"\s+", "", username)
    return username


def compact_username(value: str) -> str:
    """
    Catch deceptive forms like:
    t-o-w-n-l-i-t, t_o_w_n_l_i_t, a d m i n
    """
    return re.sub(r"[^a-z0-9]+", "", value.lower())