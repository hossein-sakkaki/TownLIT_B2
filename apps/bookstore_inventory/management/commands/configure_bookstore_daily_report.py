# apps/bookstore_inventory/management/commands/configure_bookstore_daily_report.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


PERIODIC_TASK_NAME = "TownLIT daily bookstore inventory summary"
CELERY_TASK_NAME = "apps.bookstore_inventory.tasks.send_daily_inventory_report"


class Command(BaseCommand):
    help = (
        "Create or update the django-celery-beat schedule for the daily "
        "bookstore inventory summary. This command is idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hour",
            type=int,
            default=int(getattr(settings, "BOOKSTORE_DAILY_REPORT_HOUR", 7)),
            help="Local delivery hour (0-23). Default: 7.",
        )
        parser.add_argument(
            "--minute",
            type=int,
            default=int(getattr(settings, "BOOKSTORE_DAILY_REPORT_MINUTE", 0)),
            help="Local delivery minute (0-59). Default: 0.",
        )
        parser.add_argument(
            "--timezone",
            default=getattr(
                settings,
                "BOOKSTORE_DAILY_REPORT_TIMEZONE",
                "America/Vancouver",
            ),
            help="IANA timezone used by the schedule.",
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help="Disable the existing periodic task without deleting it.",
        )

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask
        except ImportError as exc:
            raise CommandError(
                "django-celery-beat is required to configure this schedule."
            ) from exc

        if options["disable"]:
            updated = PeriodicTask.objects.filter(name=PERIODIC_TASK_NAME).update(
                enabled=False
            )
            if updated:
                self.stdout.write(self.style.WARNING("Daily bookstore report disabled."))
            else:
                self.stdout.write(self.style.WARNING("No existing daily report schedule was found."))
            return

        hour = options["hour"]
        minute = options["minute"]
        timezone_name = str(options["timezone"]).strip()
        if not 0 <= hour <= 23:
            raise CommandError("--hour must be between 0 and 23.")
        if not 0 <= minute <= 59:
            raise CommandError("--minute must be between 0 and 59.")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise CommandError(f"Unknown timezone: {timezone_name}") from exc

        schedule, _created = CrontabSchedule.objects.get_or_create(
            minute=str(minute),
            hour=str(hour),
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone=timezone_name,
        )
        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=PERIODIC_TASK_NAME,
            defaults={
                "task": CELERY_TASK_NAME,
                "crontab": schedule,
                "interval": None,
                "solar": None,
                "clocked": None,
                "args": "[]",
                "kwargs": "{}",
                "enabled": True,
                "one_off": False,
                "description": (
                    "Emails all current bookstore warehouse managers a concise "
                    "all-warehouse inventory summary."
                ),
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{action} '{periodic_task.name}' for {hour:02d}:{minute:02d} "
            f"{timezone_name}."
        ))
