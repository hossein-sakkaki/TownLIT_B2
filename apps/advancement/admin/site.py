# apps/advancement/admin/site.py

from django.contrib.admin import AdminSite
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.advancement.permissions import is_board_viewer, is_advancement_officer
from apps.advancement.services import (
    build_board_snapshot,
    build_board_snapshot_csv_response,
    build_board_snapshot_pdf_response,
)


class AdvancementAdminSite(AdminSite):
    """Dedicated admin site for advancement domain."""
    site_header = "TownLIT Advancement Administration"
    site_title = "Advancement Admin"
    index_title = "Advancement Control Panel"
    site_url = None

    def has_permission(self, request):
        return is_board_viewer(request.user)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("dashboard/", self.admin_view(self.dashboard_view), name="advancement-dashboard"),
            path(
                "dashboard/export/csv/",
                self.admin_view(self.export_board_snapshot_csv_view),
                name="advancement-dashboard-export-csv",
            ),
            path(
                "dashboard/export/pdf/",
                self.admin_view(self.export_board_snapshot_pdf_view),
                name="advancement-dashboard-export-pdf",
            ),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        """Redirect admin home to dashboard URL."""
        return HttpResponseRedirect(reverse("advancement_admin:advancement-dashboard"))

    def export_board_snapshot_csv_view(self, request):
        """Export board snapshot as CSV."""
        if not self.has_permission(request):
            return self.login(request)

        snapshot = build_board_snapshot()
        return build_board_snapshot_csv_response(snapshot)

    def export_board_snapshot_pdf_view(self, request):
        """Export board snapshot as printable PDF."""
        if not self.has_permission(request):
            return self.login(request)

        snapshot = build_board_snapshot()
        return build_board_snapshot_pdf_response(snapshot)

    def dashboard_view(self, request):
        """Render dashboard from board snapshot service (single source of truth)."""
        if not self.has_permission(request):
            return self.login(request)

        snapshot = build_board_snapshot()

        # UI-only chart rows (CSS bar widths)
        max_stage_count = max([r["count"] for r in snapshot.stage_rows], default=0)
        stage_chart_rows = []
        for row in snapshot.stage_rows:
            count = row["count"]
            width_pct = int((count / max_stage_count) * 100) if max_stage_count else 0
            stage_chart_rows.append(
                {
                    "stage": row["stage"],
                    "label": row["label"],
                    "count": count,
                    "width_pct": max(width_pct, 3) if count else 0,  # keep tiny bars visible
                }
            )

        context = dict(
            self.each_context(request),
            title="Advancement Dashboard",

            # Snapshot summary
            pledged_total=snapshot.pledged_total,
            confirmed_total=snapshot.confirmed_total,
            pipeline_value=snapshot.pipeline_value,  # planning metric (may mix currencies)
            approval_rate=snapshot.approval_rate,
            overdue_followups=snapshot.overdue_followups,
            due_today_followups=snapshot.due_today_followups,
            entity_count=snapshot.entity_count,
            opp_count=snapshot.opp_count,
            commitment_count=snapshot.commitment_count,
            active_pipeline_count=snapshot.active_pipeline_count,

            # Table rows (dict-based, template should use dict keys)
            legal_entity_totals=snapshot.legal_entity_rows,
            top_entities=snapshot.top_entity_rows,
            overdue_opportunities=snapshot.overdue_rows[:15],
            upcoming_opportunities=snapshot.upcoming_rows[:15],
            recent_interactions=snapshot.recent_interaction_rows[:8],
            stage_chart_rows=stage_chart_rows,
            stage_counts={r["stage"]: r["count"] for r in snapshot.stage_rows},

            # UI flags
            board_readonly=not is_advancement_officer(request.user),

            # Quick links
            quick_links={
                "dashboard": reverse("advancement_admin:advancement-dashboard"),
                "entities": reverse("advancement_admin:advancement_externalentity_changelist"),
                "opportunities": reverse("advancement_admin:advancement_opportunity_changelist"),
                "commitments": reverse("advancement_admin:advancement_commitment_changelist"),
                "scores": reverse("advancement_admin:advancement_strategicscore_changelist"),
                "interactions": reverse("advancement_admin:advancement_interactionlog_changelist"),
                "legal_entities": reverse("advancement_admin:advancement_legalentity_changelist"),
                "export_csv": reverse("advancement_admin:advancement-dashboard-export-csv"),
                "export_pdf": reverse("advancement_admin:advancement-dashboard-export-pdf"),
            },
        )
        return TemplateResponse(request, "admin/advancement/dashboard.html", context)


advancement_admin_site = AdvancementAdminSite(name="advancement_admin")