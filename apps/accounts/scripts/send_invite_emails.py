from django.utils.timezone import now
from django.conf import settings
from apps.accounts.models import InviteCode
from apps.moderation.models import AccessRequest
from utils.email.email_tools import send_custom_email

def send_pending_invite_emails():
    invites = InviteCode.objects.filter(invite_email_sent=False, email__isnull=False)
    sent_count = 0
    failed_count = 0

    for invite in invites:
        email = invite.email
        code = invite.code

        first_name = invite.first_name or email.split("@")[0].split(".")[0].title()
        last_name = invite.last_name or ""

        subject = f"🌟 Welcome to TownLIT, {first_name}!"

        context = {
            'first_name': first_name,
            'last_name': last_name,
            'invite_code': code,
            'email': email,
            'site_domain': settings.SITE_URL,
            "current_year": now().year,
        }

        success = send_custom_email(
            to=email,
            subject=subject,
            template_path='emails/invite/invite_email.html',
            context=context,
            text_template_path=None
        )

        if success:
            # ✅ ۱. به‌روزرسانی InviteCode
            invite.invite_email_sent = True
            invite.invite_email_sent_at = now()
            invite.save()

            # ✅ ۲. اگر رکورد مرتبطی در AccessRequest یافت شد، آن را نیز به‌روزرسانی کن
            try:
                request = AccessRequest.objects.get(email=email)
                request.invite_code_sent = True
                request.save()
            except AccessRequest.DoesNotExist:
                pass  # مشکلی نیست اگر در AccessRequest وجود نداشته باشد

            sent_count += 1
            print(f"✅ Invite sent to: {email}")
        else:
            failed_count += 1
            print(f"❌ Failed to send invite to: {email}")

    print(f"\n📤 Invite Email Summary:")
    print(f"  ✅ Sent: {sent_count}")
    print(f"  ❌ Failed: {failed_count}")



# python manage.py send_invite_emails 