# apps/accounts/management/commands/assign_invite_codes.py
from django.core.management.base import BaseCommand
from apps.accounts.scripts.assign_invite_codes import assign_codes_to_access_requests

class Command(BaseCommand):
    help = "Assign invite codes to users in AccessRequest (if active and not yet assigned)"

    def handle(self, *args, **kwargs):
        assign_codes_to_access_requests()
        self.stdout.write(self.style.SUCCESS("✅ Invite codes assigned successfully."))


# docker compose exec backend python manage.py assign_invite_codes

