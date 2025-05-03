import json
from pathlib import Path
from django.utils.html import escape
from accounts.models import InviteCode
from accounts.scripts.utils.code_tools import generate_invite_code

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "data/invite_users_data.json"

def load_users_from_json():
    with open(JSON_PATH, encoding='utf-8') as f:
        full_data = json.load(f)

    for entry in full_data:
        if entry.get('type') == 'table' and entry.get('name') == 'forms_invitemodel':
            return entry['data']
    return []

def assign_codes_to_emails():
    users = load_users_from_json()
    created_count = 0
    skipped_count = 0

    for user_data in users:
        email = user_data.get('email')
        if not email or InviteCode.objects.filter(email=email).exists():
            skipped_count += 1
            continue

        code = generate_invite_code()
        InviteCode.objects.create(code=code, email=email)
        created_count += 1
        print(f"✅ Code assigned for: {email}")

    print(f"\n📌 Summary:")
    print(f"  ✅ New invite codes created: {created_count}")
    print(f"  ⏩ Emails already in DB: {skipped_count}")
