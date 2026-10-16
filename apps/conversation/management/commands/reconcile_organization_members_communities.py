# apps/conversation/management/commands/reconcile_organization_members_communities.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.core.management.base import BaseCommand, CommandError

from apps.conversation.services.organization import (
    reconcile_organization_members_community,
)
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = (
        "Ensure canonical Organization Members Communities and reconcile "
        "official membership/runtime access."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            dest="slug",
            default=None,
            help="Reconcile one Organization by slug.",
        )

    def handle(self, *args, **options):
        queryset = Organization.objects.all().order_by("id")

        slug = str(options.get("slug") or "").strip()
        if slug:
            queryset = queryset.filter(slug=slug)
            if not queryset.exists():
                raise CommandError(f"Organization not found: {slug}")

        processed = 0
        available = 0
        created = 0
        members = 0
        added = 0
        removed = 0
        updated = 0

        for organization in queryset.iterator():
            result = reconcile_organization_members_community(
                organization=organization,
                emit_visibility_event=True,
            )
            processed += 1
            available += int(result.available)
            created += int(result.created)
            members += result.member_count
            added += result.added_count
            removed += result.removed_count
            updated += result.updated_count

        self.stdout.write(
            self.style.SUCCESS(
                "Organization Members Community reconciliation complete: "
                f"processed={processed} available={available} "
                f"created={created} members={members} "
                f"added={added} removed={removed} updated={updated}"
            )
        )
