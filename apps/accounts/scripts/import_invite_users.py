import json
from pathlib import Path
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive
from apps.moderation.models import AccessRequest


def import_invite_users_from_json(file_path):
    full_path = Path(file_path)
    with open(full_path, "r", encoding="utf-8") as f:
        full_data = json.load(f)

    created = 0
    skipped = 0

    for block in full_data:
        if block.get("type") == "table" and block.get("name") == "forms_invitemodel":
            table_data = block.get("data", [])
            break
    else:
        print("❌ Table 'forms_invitemodel' not found.")
        return

    for entry in table_data:
        email = entry.get("email")
        if not email or AccessRequest.objects.filter(email=email).exists():
            skipped += 1
            continue

        # Parse and normalize datetime
        raw_date = entry.get("registre_date")
        parsed_date = parse_datetime(raw_date) if raw_date else None
        if parsed_date and is_naive(parsed_date):
            parsed_date = make_aware(parsed_date)
        submitted = parsed_date or timezone.now()

        AccessRequest.objects.create(
            first_name=entry.get("name", "").strip(),
            last_name=entry.get("family", "").strip(),
            email=email.strip(),
            country=entry.get("nation", "").strip(),
            how_found_us=entry.get("recognize", "").strip(),
            message="",
            status="new",
            is_active=True,
            submitted_at=submitted
        )
        created += 1

    print(f"✅ Imported: {created}, Skipped (duplicates): {skipped}")

    


# temporary - deleted after use
# python manage.py import_invite_users
