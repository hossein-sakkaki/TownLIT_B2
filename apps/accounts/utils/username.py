# accounts/utils/username.py

import re
from django.utils.text import slugify
from django.db.models import Q

def generate_unique_username_from_email(email: str, model_cls) -> str:
    """
    Generate a unique username from email local-part.
    Example:
      sakkaki.hossein@gmail.com -> sakkaki.hossein
      sakkaki.hossein@yahoo.com -> sakkaki.hossein_1
    """
    if not email or "@" not in email:
        raise ValueError("Valid email is required to generate username")

    # Take local part before @
    local_part = email.split("@")[0]

    # Slugify but keep dots if you want (optional)
    base = slugify(local_part.replace(".", "-")).replace("-", ".")

    if not base:
        base = "user"

    # Fast path: if not exists, return directly
    if not model_cls.objects.filter(username=base).exists():
        return base

    # Find all usernames with same base or base_N
    pattern = rf"^{re.escape(base)}_(\d+)$"

    existing = (
        model_cls.objects
        .filter(Q(username=base) | Q(username__regex=pattern))
        .values_list("username", flat=True)
    )

    # Collect used suffixes
    used = set()
    for u in existing:
        if u == base:
            used.add(0)
        else:
            try:
                used.add(int(u.split("_")[-1]))
            except ValueError:
                continue

    # Find smallest available suffix
    i = 1
    while i in used:
        i += 1

    return f"{base}_{i}"
