# apps/accounts/management/commands/import_invite_users.py

from django.core.management.base import BaseCommand
from apps.accounts.scripts.import_invite_users import import_invite_users_from_json


class Command(BaseCommand):
    help = "Import invite users from fixed JSON file into AccessRequest"

    def handle(self, *args, **kwargs):
        file_path = "apps/accounts/scripts/data/invite_users_data.json"
        import_invite_users_from_json(file_path)
        self.stdout.write(self.style.SUCCESS("✅ Invite users imported from fixed path."))


# temporary - deleted after use