from django.utils.html import escape
from django.utils.timezone import now
from apps.accounts.models import InviteCode
from apps.moderation.models import AccessRequest
from apps.accounts.scripts.utils.code_tools import generate_invite_code

def assign_codes_to_access_requests():
    created_count = 0
    skipped_count = 0

    requests = AccessRequest.objects.filter(
        is_active=True,
        invite_code_sent=False
    ).exclude(email__in=InviteCode.objects.values_list('email', flat=True))

    for request in requests:
        email = request.email
        first_name = escape(request.first_name.strip().title())
        last_name = escape(request.last_name.strip().title())

        code = generate_invite_code()

        InviteCode.objects.create(
            code=code,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        created_count += 1
        print(f"✅ Code assigned for: {email}")

    skipped_count = AccessRequest.objects.filter(
        is_active=True
    ).filter(
        email__in=InviteCode.objects.values_list('email', flat=True)
    ).count()

    print("\n📌 Summary:")
    print(f"  ✅ New invite codes created: {created_count}")
    print(f"  ⏩ Skipped (already in InviteCode): {skipped_count}")



# python manage.py assign_invite_codes 