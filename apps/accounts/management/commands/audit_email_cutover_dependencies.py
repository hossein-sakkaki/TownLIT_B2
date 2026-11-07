# apps/accounts/management/commands/audit_email_cutover_dependencies.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Static preflight for removing CustomUser.email as a concrete DB column.

This report is intentionally conservative: source text alone cannot prove an
ORM field's owning model. Results are candidates requiring engineering review,
not authorization to execute a destructive migration. No PII is read.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


# The primary blockers will require the final email-property transition.
CRITICAL = (
    re.compile(r"\bUSERNAME_FIELD\s*=\s*['\"]email['\"]"),
    re.compile(r"\bemail\s*=\s*models\.EmailField\("),
    re.compile(r"\bfields\s*=\s*\[[^\]]*['\"]email['\"]", re.DOTALL),
)
# Reference patterns whose target model needs case-by-case evaluation.
REVIEW = (
    re.compile(r"\b[A-Za-z_]+(?:__[A-Za-z_]+)*__email\b"),
    re.compile(r"\bemail__(?:iexact|exact|in|icontains|contains|isnull)\b"),
    re.compile(r"\bemail\.admin_order_field\b"),
)
SKIP_DIRS = {"migrations", "tests", "__pycache__", "node_modules", ".venv", "venv"}


class Command(BaseCommand):
    help = "Read-only report of source dependencies before CustomUser.email DB cutover."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Fail if critical blockers remain")
        parser.add_argument("--limit", type=int, default=120, help="Maximum candidate lines to print")

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR) / "apps"
        critical = []
        review = []
        for file in sorted(root.rglob("*.py")):
            if any(piece in SKIP_DIRS for piece in file.relative_to(root).parts):
                continue
            if file.name == "audit_email_cutover_dependencies.py":
                continue
            source = file.read_text(encoding="utf-8", errors="replace")
            # Only CustomUser's field/username configuration is a definite
            # cutover blocker. Other apps intentionally own their own email
            # fields (communication, accounting, vendors, etc.).
            relative = str(file.relative_to(root))
            for number, line in enumerate(source.splitlines(), 1):
                if relative == "accounts/models/user.py" and any(
                    pattern.search(line) for pattern in CRITICAL[:2]
                ):
                    critical.append(f"{relative}:{number}")
                elif any(pattern.search(line) for pattern in REVIEW):
                    review.append(f"{relative}:{number}")

        self.stdout.write(f"critical_candidates={len(critical)} review_candidates={len(review)}")
        limit = max(0, min(int(options["limit"]), 1000))
        for loc in critical[:limit]:
            self.stdout.write(f"CRITICAL {loc}")
        remaining = max(0, limit - len(critical))
        for loc in review[:remaining]:
            self.stdout.write(f"REVIEW {loc}")
        if critical:
            self.stdout.write(self.style.WARNING(
                "NOT_READY: Do not remove the plaintext email column."
            ))
            if options["strict"]:
                raise CommandError("Critical email-cutover candidates remain")
        else:
            self.stdout.write(self.style.WARNING(
                "No obvious critical candidates; full manual source and DB audit is still required."
            ))
