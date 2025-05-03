from django.utils.timezone import now
from django.template.loader import render_to_string
from accounts.models import InviteCode
from utils.common.utils import send_email  # از سیستم AWS SES تو استفاده می‌کنیم

def send_pending_invite_emails():
    invites = InviteCode.objects.filter(invite_email_sent=False, email__isnull=False)
    sent_count = 0
    failed_count = 0

    for invite in invites:
        email = invite.email
        code = invite.code
        name_part = email.split("@")[0].replace(".", " ").title()
        full_name = name_part if name_part else "Friend"

        subject = f"Welcome to TownLIT, {full_name}!"
        email_body = render_to_string('emails/invite/invite_email.html', {
            'full_name': full_name,
            'invite_code': code,
            'email': email
        })

        success = send_email(subject, "", email_body, email)
        if success:
            invite.invite_email_sent = True
            invite.invite_email_sent_at = now()
            invite.save()
            sent_count += 1
            print(f"✅ Invite sent to: {email}")
        else:
            failed_count += 1
            print(f"❌ Failed to send invite to: {email}")

    print(f"\n📤 Invite Email Summary:")
    print(f"  ✅ Sent: {sent_count}")
    print(f"  ❌ Failed: {failed_count}")



# python manage.py shell

# from accounts.scripts.send_invite_emails import send_pending_invite_emails
# send_pending_invite_emails()