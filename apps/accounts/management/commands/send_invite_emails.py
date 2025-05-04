from django.core.management.base import BaseCommand
from apps.accounts.scripts.send_invite_emails import send_pending_invite_emails

class Command(BaseCommand):
    help = "Send pending invite emails to users with assigned codes"

    def handle(self, *args, **kwargs):
        send_pending_invite_emails()
        self.stdout.write(self.style.SUCCESS("✅ Invite emails sent."))

# python manage.py send_invite_emails
