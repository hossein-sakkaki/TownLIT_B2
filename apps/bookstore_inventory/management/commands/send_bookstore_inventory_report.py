# apps/bookstore_inventory/management/commands/send_bookstore_inventory_report.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.management.base import BaseCommand, CommandError

from apps.bookstore_inventory.services.daily_reports import (
    send_daily_inventory_summary,
)


class Command(BaseCommand):
    help = "Preview or immediately send the daily bookstore inventory summary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build the report and show recipients without sending email.",
        )
        parser.add_argument(
            "--email",
            action="append",
            dest="emails",
            help=(
                "Send only to this email address. Repeat the option for multiple "
                "test recipients."
            ),
        )

    def handle(self, *args, **options):
        result = send_daily_inventory_summary(
            override_emails=options.get("emails"),
            dry_run=options["dry_run"],
        )
        if result["status"] == "disabled":
            raise CommandError(
                "BOOKSTORE_DAILY_REPORT_ENABLED is false; no email was sent."
            )
        if result["status"] == "dry_run":
            self.stdout.write(self.style.WARNING(
                f"Dry run: {result['recipients']} recipient(s), "
                f"{result['warehouse_count']} warehouse(s), "
                f"{result['available']} available book(s)."
            ))
            for email in result["emails"]:
                self.stdout.write(f"- {email}")
            return
        if result["status"] == "no_recipients":
            self.stdout.write(self.style.WARNING(
                "No current warehouse manager with an email address was found."
            ))
            return
        message = (
            f"Inventory summary completed: {result['sent']} sent, "
            f"{result['failed']} failed."
        )
        if result["failed"]:
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
