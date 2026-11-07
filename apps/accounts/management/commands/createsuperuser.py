# apps/accounts/management/commands/createsuperuser.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""TownLIT superuser creation after email becomes a non-model property.

Django's default createsuperuser prompts only for USERNAME_FIELD and concrete
REQUIRED_FIELDS. Email is neither, so this command also prompts for email.
"""

import getpass
import os

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import DEFAULT_DB_ALIAS, connections

from apps.accounts.services.email_lookup import user_email_q


class Command(BaseCommand):
    help = "Create a TownLIT superuser with a verified unique username and protected email."

    def add_arguments(self, parser):
        parser.add_argument("--username", dest="username")
        parser.add_argument("--email", dest="email")
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS, choices=connections)
        parser.add_argument("--noinput", "--no-input", action="store_false", dest="interactive")

    def handle(self, *args, **options):
        User = get_user_model()
        database = options["database"]
        interactive = options.get("interactive", True)
        username = (options.get("username") or os.environ.get("DJANGO_SUPERUSER_USERNAME") or "").strip()
        email = (options.get("email") or os.environ.get("DJANGO_SUPERUSER_EMAIL") or "").strip()
        password = None

        if interactive:
            if not username:
                username = input("Username: ").strip()
            if not email:
                email = input("Email: ").strip()
        else:
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not email:
            raise CommandError("Username and email are required.")
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Invalid email format.") from exc
        if len(username) > User._meta.get_field("username").max_length:
            raise CommandError("Username exceeds the allowed length.")

        manager = User._default_manager.db_manager(database)
        if manager.filter(username__iexact=username).exists():
            raise CommandError("Username is already in use.")
        if manager.filter(user_email_q(email)).exists():
            raise CommandError("Email is already in use.")

        candidate = User(username=username, email=email)
        if interactive:
            password = getpass.getpass("Password: ")
            confirmation = getpass.getpass("Password (again): ")
            if password != confirmation:
                raise CommandError("Passwords do not match.")
        if not password:
            raise CommandError("Password is required; in --noinput mode use DJANGO_SUPERUSER_PASSWORD.")
        try:
            password_validation.validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError("Password does not meet the configured policy.") from exc

        try:
            user = manager.create_superuser(username=username, email=email, password=password)
        except Exception as exc:
            # Do not include raw exception or email in CLI output.
            raise CommandError("Could not create superuser.") from exc
        self.stdout.write(self.style.SUCCESS(f"Superuser created: user_id={user.pk}"))
