from django.core.management.base import BaseCommand
from apps.accounts.scripts.assign_invite_codes import assign_codes_to_emails

class Command(BaseCommand):
    help = "Assign invite codes to users listed in JSON file"

    def handle(self, *args, **kwargs):
        assign_codes_to_emails()
        self.stdout.write(self.style.SUCCESS('✅ Invite codes assigned successfully.'))


# python manage.py assign_invite_codes
