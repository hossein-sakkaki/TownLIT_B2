# apps/organizations/management/commands/sync_organization_comment_permission.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.organizations.constants import OrganizationPermissionKey, OrganizationRoleKey
from apps.organizations.models import (
    OrganizationPermission, OrganizationRole, OrganizationRolePermission,
)


class Command(BaseCommand):
    help = "Grant organization comment identity to existing built-in publishing roles."

    @transaction.atomic
    def handle(self, *args, **options):
        permission, _ = OrganizationPermission.objects.update_or_create(
            key=OrganizationPermissionKey.REPLY_COMMENTS,
            defaults={
                "name": "Reply to Comments as Organization",
                "category": "content",
                "is_active": True,
            },
        )
        roles = OrganizationRole.objects.filter(
            is_system=True,
            key__in=(
                OrganizationRoleKey.OWNER,
                OrganizationRoleKey.ADMINISTRATOR,
                OrganizationRoleKey.CONTENT_MANAGER,
            ),
        )
        count = 0
        for role in roles.iterator():
            _, created = OrganizationRolePermission.objects.get_or_create(
                role=role, permission=permission,
            )
            count += int(created)
        self.stdout.write(self.style.SUCCESS(f"Added {count} role grants."))
