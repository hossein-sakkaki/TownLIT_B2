# apps/organizations/management/commands/diagnose_organization_discovery.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.urls import Resolver404, resolve

from apps.organizations.constants import OrganizationStatus, OrganizationVisibility
from apps.organizations.feature_flags import organizations_enabled
from apps.organizations.models import Organization
from apps.organizations.selectors.discovery import OrganizationDiscoveryService
from apps.organizations.serializers.discovery import OrganizationDiscoveryResultSerializer
from apps.organizations.views.discovery import OrganizationDiscoveryView


class Command(BaseCommand):
    help = "Read-only diagnosis of TownLIT Organization discovery and its API route."

    def add_arguments(self, parser):
        parser.add_argument("--query", default="TownLIT", help="Organization search phrase")
        parser.add_argument("--slug", default="", help="Optional exact Organization slug")

    def handle(self, *args, **options):
        query = " ".join(options["query"].split())
        slug = options["slug"].strip()
        if len(query) < 2:
            self.stderr.write("Use a query of at least two characters.")
            return

        self.stdout.write(f"Search query: {query!r}")
        self._check_route()
        self.stdout.write(f"Organizations enabled: {organizations_enabled()}")
        self.stdout.write(
            "iOS client enabled: "
            f"{bool(getattr(settings, 'TOWNLIT_ORGANIZATIONS_IOS_ENABLED', False))}"
        )

        base = Organization.objects.all()
        eligible = base.filter(
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
        )
        basic_match = (
            Q(name__icontains=query)
            | Q(short_name__icontains=query)
            | Q(slug__icontains=query)
        )
        matching = base.filter(basic_match)
        matching_public = eligible.filter(basic_match)

        self.stdout.write(f"Database Organizations: {base.count()}")
        self.stdout.write(f"Active + public: {eligible.count()}")
        self.stdout.write(f"Name/short name/slug matches: {matching.count()}")
        self.stdout.write(f"Eligible identity matches: {matching_public.count()}")
        for organization in matching.order_by("id")[:10]:
            self._print_organization(organization)

        if slug:
            exact = base.filter(slug=slug).first()
            if exact is None:
                self.stdout.write(f"Exact slug {slug!r}: NOT IN DATABASE")
            else:
                self.stdout.write(f"Exact slug {slug!r}:")
                self._print_organization(exact)

        try:
            results = OrganizationDiscoveryService.search(query=query)
        except Exception as exc:
            self.stderr.write(
                f"Discovery service ERROR: {type(exc).__name__}: {exc}"
            )
            return

        self.stdout.write(f"Discovery service results: {len(results)}")
        for organization in results[:10]:
            self._print_organization(organization)

        try:
            data = OrganizationDiscoveryResultSerializer(
                results[:1], many=True
            ).data
            self.stdout.write(f"Serialization: OK ({len(data)} sample rows)")
            if data:
                keys = ", ".join(sorted(data[0].keys()))
                self.stdout.write(f"Response fields: {keys}")
        except Exception as exc:
            self.stderr.write(
                f"Serialization ERROR: {type(exc).__name__}: {exc}"
            )
            return

        if not organizations_enabled():
            self.stderr.write("DIAGNOSIS: API is blocked by the global feature flag.")
        elif matching.exists() and not matching_public.exists():
            self.stderr.write(
                "DIAGNOSIS: matching records are not active + public. "
                "Check Organization visibility and lifecycle."
            )
        elif matching_public.exists() and not results:
            self.stderr.write(
                "DIAGNOSIS: eligible identity matches exist but discovery "
                "did not return them; investigate query matching/SQL."
            )
        elif results:
            self.stdout.write(
                "DIAGNOSIS: backend service returns Organizations. "
                "If iOS is empty, inspect real HTTP status/response and decoding."
            )
        else:
            self.stdout.write(
                "DIAGNOSIS: no eligible identity matches. Try the exact "
                "slug or a known Organization name."
            )

    def _check_route(self):
        path = "/api/v1/organizations/discovery/"
        try:
            match = resolve(path)
        except Resolver404:
            self.stderr.write(f"ROUTE MISSING: {path}")
            return

        resolved_class = getattr(match.func, "view_class", None)
        if resolved_class is OrganizationDiscoveryView:
            self.stdout.write(f"Route: OK ({path})")
        else:
            self.stderr.write(
                f"ROUTE MISMATCH: {path} resolves to "
                f"{resolved_class or match.func!r}; expected OrganizationDiscoveryView"
            )

    def _print_organization(self, organization):
        self.stdout.write(
            "  "
            f"id={organization.pk} "
            f"slug={organization.slug!r} "
            f"name={organization.name!r} "
            f"status={organization.status!r} "
            f"visibility={organization.visibility!r}"
        )
