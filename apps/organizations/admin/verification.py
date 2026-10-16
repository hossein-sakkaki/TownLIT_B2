# apps/organizations/admin/verification.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

from django.contrib import admin, messages
from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.organizations.constants import (
    OrganizationVerificationDocumentReviewStatus,
    OrganizationVerificationGrantStatus,
    OrganizationVerificationStatus,
)
from apps.organizations.models import (
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
    OrganizationVerificationGrant,
)
from apps.organizations.services.verification import (
    approve_verification_case,
    mark_verification_needs_information,
    reject_verification_case,
    review_verification_document,
    revoke_verification_grant,
    start_verification_review,
)

from .private_files import build_verification_document_url

from .forms import (
    VerificationCaseWorkflowForm,
    VerificationDocumentWorkflowForm,
    VerificationGrantRevokeForm,
)


WORKFLOW_TEMPLATE = "admin/organizations/workflow_form.html"


def _validation_error_text(exc):
    if getattr(exc, "message_dict", None):
        parts = []
        for field, values in exc.message_dict.items():
            for value in values:
                parts.append(f"{field}: {value}")
        return " ".join(parts)

    messages_list = getattr(exc, "messages", None)
    if messages_list:
        return " ".join(str(message) for message in messages_list)

    return str(exc)


class VerificationQueueFilter(admin.SimpleListFilter):
    title = "review queue"
    parameter_name = "review_queue"

    def lookups(self, request, model_admin):
        return (
            ("actionable", "Actionable review"),
            ("waiting_org", "Waiting for organization"),
            ("completed", "Completed"),
        )

    def queryset(self, request, queryset):
        value = self.value()

        if value == "actionable":
            return queryset.filter(
                status__in=(
                    OrganizationVerificationStatus.SUBMITTED,
                    OrganizationVerificationStatus.UNDER_REVIEW,
                )
            )

        if value == "waiting_org":
            return queryset.filter(
                status=OrganizationVerificationStatus.NEEDS_INFORMATION
            )

        if value == "completed":
            return queryset.filter(
                status__in=(
                    OrganizationVerificationStatus.APPROVED,
                    OrganizationVerificationStatus.REJECTED,
                    OrganizationVerificationStatus.WITHDRAWN,
                )
            )

        return queryset


class OrganizationVerificationDocumentInline(admin.TabularInline):
    model = OrganizationVerificationDocument
    extra = 0
    can_delete = False
    show_change_link = True

    fields = (
        "document_type",
        "title",
        "file_link",
        "document_number",
        "issued_at",
        "expires_at",
        "review_status",
        "review_note",
        "reviewed_by",
        "reviewed_at",
        "is_active",
        "created_at",
    )

    readonly_fields = fields

    @admin.display(description="Secure file")
    def file_link(self, obj):
        if not obj or not obj.pk or not obj.file:
            return "—"

        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener">'
            "Open secure document</a>",
            reverse(
                "admin:organizations_organizationverificationdocument_open",
                args=(obj.pk,),
            ),
        )

    def has_add_permission(self, request, obj=None):
        return False


class OrganizationVerificationGrantInline(admin.TabularInline):
    model = OrganizationVerificationGrant
    fk_name = "verification_case"
    extra = 0
    can_delete = False
    show_change_link = True

    fields = (
        "grant_type",
        "status",
        "granted_by",
        "granted_at",
        "expires_at",
        "revoked_at",
        "revocation_reason",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OrganizationVerificationCase)
class OrganizationVerificationCaseAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "path",
        "status_badge",
        "document_review_progress",
        "submitted_at",
        "reviewed_by",
        "decision_at",
        "workflow_button",
    )
    list_filter = (
        VerificationQueueFilter,
        "path",
        "status",
        "jurisdiction_country",
    )
    search_fields = (
        "organization__name",
        "organization__slug",
        "public_id",
        "legal_name",
        "registration_number",
        "submitted_by__email",
        "reviewed_by__email",
    )
    ordering = ("-submitted_at", "-created_at", "-id")
    list_select_related = (
        "organization",
        "relationship",
        "submitted_by",
        "reviewed_by",
    )
    list_per_page = 50
    show_full_result_count = False
    date_hierarchy = "submitted_at"

    inlines = (
        OrganizationVerificationDocumentInline,
        OrganizationVerificationGrantInline,
    )

    readonly_fields = tuple(
        field.name
        for field in OrganizationVerificationCase._meta.fields
    ) + (
        "verification_summary",
        "workflow_actions",
    )

    fieldsets = (
        (
            "Review",
            {
                "fields": (
                    "verification_summary",
                    "workflow_actions",
                    "status",
                    "path",
                    "review_notes",
                    "reviewed_by",
                    "review_started_at",
                    "decision_at",
                ),
            },
        ),
        (
            "Organization & legal identity",
            {
                "fields": (
                    "organization",
                    "public_id",
                    "legal_name",
                    "registration_number",
                    "jurisdiction_country",
                    "jurisdiction_region",
                    "registration_authority",
                    "registered_address",
                ),
            },
        ),
        (
            "Submission",
            {
                "fields": (
                    "organization_notes",
                    "submitted_by",
                    "submitted_at",
                    "relationship",
                    "renewal_of",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "current_slot",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    actions = ("start_selected_reviews",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _active_document_count=Count(
                    "documents",
                    filter=Q(documents__is_active=True),
                    distinct=True,
                ),
                _accepted_document_count=Count(
                    "documents",
                    filter=Q(
                        documents__is_active=True,
                        documents__review_status=(
                            OrganizationVerificationDocumentReviewStatus.ACCEPTED
                        ),
                    ),
                    distinct=True,
                ),
                _rejected_document_count=Count(
                    "documents",
                    filter=Q(
                        documents__is_active=True,
                        documents__review_status=(
                            OrganizationVerificationDocumentReviewStatus.REJECTED
                        ),
                    ),
                    distinct=True,
                ),
            )
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            OrganizationVerificationStatus.DRAFT: "#6c757d",
            OrganizationVerificationStatus.SUBMITTED: "#0d6efd",
            OrganizationVerificationStatus.UNDER_REVIEW: "#6f42c1",
            OrganizationVerificationStatus.NEEDS_INFORMATION: "#fd7e14",
            OrganizationVerificationStatus.APPROVED: "#198754",
            OrganizationVerificationStatus.REJECTED: "#dc3545",
            OrganizationVerificationStatus.WITHDRAWN: "#495057",
        }

        color = colors.get(obj.status, "#6c757d")
        label = obj.get_status_display()

        return format_html(
            '<span style="display:inline-block;padding:2px 8px;'
            'border-radius:999px;background:{};color:#fff;font-weight:600;">'
            "{}</span>",
            color,
            label,
        )

    @admin.display(description="Documents")
    def document_review_progress(self, obj):
        active = getattr(obj, "_active_document_count", 0)
        accepted = getattr(obj, "_accepted_document_count", 0)
        rejected = getattr(obj, "_rejected_document_count", 0)

        if not active:
            return format_html(
                '<span style="color:#dc3545;font-weight:600;">0 active</span>'
            )

        if rejected:
            return format_html(
                '<span style="color:#dc3545;font-weight:600;">'
                "{} accepted / {} active · {} rejected</span>",
                accepted,
                active,
                rejected,
            )

        if accepted == active:
            return format_html(
                '<span style="color:#198754;font-weight:600;">'
                "{} / {} accepted</span>",
                accepted,
                active,
            )

        return format_html(
            '<span style="color:#6c757d;">{} / {} accepted</span>',
            accepted,
            active,
        )

    @admin.display(description="Summary")
    def verification_summary(self, obj):
        if not obj:
            return "—"

        active_documents = obj.documents.filter(is_active=True)
        accepted = active_documents.filter(
            review_status=OrganizationVerificationDocumentReviewStatus.ACCEPTED
        ).count()
        rejected = active_documents.filter(
            review_status=OrganizationVerificationDocumentReviewStatus.REJECTED
        ).count()
        total = active_documents.count()

        text = (
            f"Active documents: {total} · "
            f"Accepted: {accepted} · "
            f"Rejected: {rejected}"
        )
        return text

    @admin.display(description="Workflow")
    def workflow_button(self, obj):
        if not VerificationCaseWorkflowForm.has_available_action(obj):
            return "—"

        return format_html(
            '<a class="button" href="{}">Review / Decision</a>',
            self._workflow_url(obj),
        )

    @admin.display(description="Workflow actions")
    def workflow_actions(self, obj):
        if not obj:
            return "Save the case before using workflow actions."

        if not VerificationCaseWorkflowForm.has_available_action(obj):
            return format_html(
                "<strong>No review action is available for this status.</strong>"
            )

        return format_html(
            '<a class="button" href="{}">Open review workflow</a>',
            self._workflow_url(obj),
        )

    def _workflow_url(self, obj):
        return reverse(
            "admin:organizations_organizationverificationcase_workflow",
            args=(obj.pk,),
        )

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "<path:object_id>/workflow/",
                self.admin_site.admin_view(self.workflow_view),
                name="organizations_organizationverificationcase_workflow",
            ),
        ]
        return custom_urls + urls

    def workflow_view(self, request, object_id):
        verification_case = self.get_object(request, object_id)

        if verification_case is None:
            raise Http404("Verification case not found.")

        if not self.has_change_permission(request, verification_case):
            raise PermissionDenied

        form = VerificationCaseWorkflowForm(
            request.POST or None,
            verification_case=verification_case,
        )

        if request.method == "POST" and form.is_valid():
            action = form.cleaned_data["action"]
            review_notes = form.cleaned_data.get("review_notes")
            expires_at = form.cleaned_data.get("expires_at")

            try:
                if action == VerificationCaseWorkflowForm.ACTION_START_REVIEW:
                    start_verification_review(
                        verification_case=verification_case,
                        reviewer=request.user,
                    )
                    success_message = "Verification review started."

                elif action == VerificationCaseWorkflowForm.ACTION_NEEDS_INFORMATION:
                    mark_verification_needs_information(
                        verification_case=verification_case,
                        reviewer=request.user,
                        review_notes=review_notes,
                    )
                    success_message = (
                        "Verification case returned for more information."
                    )

                elif action == VerificationCaseWorkflowForm.ACTION_APPROVE:
                    approve_verification_case(
                        verification_case=verification_case,
                        reviewer=request.user,
                        expires_at=expires_at,
                    )
                    success_message = "Organization verification approved."

                elif action == VerificationCaseWorkflowForm.ACTION_REJECT:
                    reject_verification_case(
                        verification_case=verification_case,
                        reviewer=request.user,
                        review_notes=review_notes,
                    )
                    success_message = "Organization verification rejected."

                else:
                    raise ValidationError("Unsupported verification action.")

            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, _validation_error_text(exc))
            else:
                self.message_user(
                    request,
                    success_message,
                    level=messages.SUCCESS,
                )
                return redirect(
                    reverse(
                        "admin:organizations_organizationverificationcase_change",
                        args=(verification_case.pk,),
                    )
                )

        documents = list(
            verification_case.documents
            .select_related("reviewed_by", "uploaded_by")
            .order_by("created_at", "id")
        )
        document_rows = [
            {
                "document": document,
                "open_url": reverse(
                    "admin:organizations_organizationverificationdocument_open",
                    args=(document.pk,),
                ),
                "download_url": reverse(
                    "admin:organizations_organizationverificationdocument_download",
                    args=(document.pk,),
                ),
                "review_url": reverse(
                    "admin:organizations_organizationverificationdocument_workflow",
                    args=(document.pk,),
                ),
            }
            for document in documents
        ]

        context = {
            **self.admin_site.each_context(request),
            "title": f"Verification workflow — {verification_case.organization}",
            "opts": self.model._meta,
            "original": verification_case,
            "form": form,
            "document_rows": document_rows,
            "media": self.media + form.media,
            "submit_label": "Apply verification action",
            "back_url": reverse(
                "admin:organizations_organizationverificationcase_change",
                args=(verification_case.pk,),
            ),
            "help_text": (
                "All changes on this page use the Organization verification "
                "service layer and create the normal audit trail."
            ),
        }

        return TemplateResponse(
            request,
            WORKFLOW_TEMPLATE,
            context,
        )

    @admin.action(description="Start review for selected submitted cases")
    def start_selected_reviews(self, request, queryset):
        started = 0
        skipped = 0

        for verification_case in queryset.select_related("organization"):
            try:
                start_verification_review(
                    verification_case=verification_case,
                    reviewer=request.user,
                )
            except (ValidationError, PermissionDenied):
                skipped += 1
            else:
                started += 1

        if started:
            self.message_user(
                request,
                f"Started review for {started} verification case(s).",
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} case(s) because their current state "
                "does not allow review to start.",
                level=messages.WARNING,
            )


@admin.register(OrganizationVerificationDocument)
class OrganizationVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "organization_name",
        "document_type",
        "title",
        "review_status_badge",
        "is_active",
        "reviewed_by",
        "reviewed_at",
        "workflow_button",
    )
    list_filter = (
        "document_type",
        "review_status",
        "is_active",
        "verification_case__status",
    )
    search_fields = (
        "verification_case__organization__name",
        "verification_case__organization__slug",
        "verification_case__public_id",
        "public_id",
        "document_number",
        "title",
    )
    list_select_related = (
        "verification_case__organization",
        "uploaded_by",
        "reviewed_by",
    )
    ordering = ("-created_at", "-id")
    list_per_page = 50
    show_full_result_count = False
    date_hierarchy = "created_at"

    readonly_fields = tuple(
        field.name
        for field in OrganizationVerificationDocument._meta.fields
    ) + (
        "file_link",
        "workflow_actions",
    )

    fieldsets = (
        (
            "Document",
            {
                "fields": (
                    "verification_case",
                    "public_id",
                    "document_type",
                    "title",
                    "file_link",
                    "document_number",
                    "issued_at",
                    "expires_at",
                    "is_active",
                ),
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "workflow_actions",
                    "review_status",
                    "review_note",
                    "reviewed_by",
                    "reviewed_at",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "uploaded_by",
                    "superseded_by",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    actions = ("accept_selected_documents",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Organization")
    def organization_name(self, obj):
        return obj.verification_case.organization.name

    @admin.display(description="Review status", ordering="review_status")
    def review_status_badge(self, obj):
        colors = {
            OrganizationVerificationDocumentReviewStatus.PENDING: "#6c757d",
            OrganizationVerificationDocumentReviewStatus.ACCEPTED: "#198754",
            OrganizationVerificationDocumentReviewStatus.REJECTED: "#dc3545",
        }

        return format_html(
            '<span style="display:inline-block;padding:2px 8px;'
            'border-radius:999px;background:{};color:#fff;font-weight:600;">'
            "{}</span>",
            colors.get(obj.review_status, "#6c757d"),
            obj.get_review_status_display(),
        )

    @admin.display(description="Secure file")
    def file_link(self, obj):
        if not obj or not obj.pk or not obj.file:
            return "—"

        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener">'
            "Open secure document</a> "
            '<a class="button" href="{}">Download</a>',
            self._secure_file_url(obj),
            self._secure_file_url(obj, download=True),
        )

    @admin.display(description="Workflow")
    def workflow_button(self, obj):
        if not obj.is_active:
            return "—"

        return format_html(
            '<a class="button" href="{}">Review</a>',
            self._workflow_url(obj),
        )

    @admin.display(description="Workflow actions")
    def workflow_actions(self, obj):
        if not obj:
            return "—"

        if not obj.is_active:
            return "This document is inactive and cannot be reviewed."

        return format_html(
            '<a class="button" href="{}">Review document</a>',
            self._workflow_url(obj),
        )

    def _workflow_url(self, obj):
        return reverse(
            "admin:organizations_organizationverificationdocument_workflow",
            args=(obj.pk,),
        )

    def _secure_file_url(self, obj, *, download=False):
        view_name = (
            "admin:organizations_organizationverificationdocument_download"
            if download
            else "admin:organizations_organizationverificationdocument_open"
        )
        return reverse(view_name, args=(obj.pk,))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/open/",
                self.admin_site.admin_view(self.secure_file_view),
                name="organizations_organizationverificationdocument_open",
            ),
            path(
                "<path:object_id>/download/",
                self.admin_site.admin_view(self.secure_file_download_view),
                name="organizations_organizationverificationdocument_download",
            ),
            path(
                "<path:object_id>/workflow/",
                self.admin_site.admin_view(self.workflow_view),
                name="organizations_organizationverificationdocument_workflow",
            ),
        ]
        return custom_urls + urls

    def _secure_file_redirect(self, request, object_id, *, attachment):
        document = self.get_object(request, object_id)

        if document is None:
            raise Http404("Verification document not found.")

        if not self.has_view_permission(request, document):
            raise PermissionDenied

        if not document.file:
            raise Http404("Verification document file is unavailable.")

        try:
            signed_url = build_verification_document_url(
                document.file,
                attachment=attachment,
            )
        except (ValueError, ImproperlyConfigured) as exc:
            raise Http404(str(exc)) from exc

        response = HttpResponseRedirect(signed_url)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response

    def secure_file_view(self, request, object_id):
        return self._secure_file_redirect(
            request,
            object_id,
            attachment=False,
        )

    def secure_file_download_view(self, request, object_id):
        return self._secure_file_redirect(
            request,
            object_id,
            attachment=True,
        )

    def workflow_view(self, request, object_id):
        document = self.get_object(request, object_id)

        if document is None:
            raise Http404("Verification document not found.")

        if not self.has_change_permission(request, document):
            raise PermissionDenied

        form = VerificationDocumentWorkflowForm(
            request.POST or None,
            document=document,
        )

        if request.method == "POST" and form.is_valid():
            accepted = (
                form.cleaned_data["action"]
                == VerificationDocumentWorkflowForm.ACTION_ACCEPT
            )
            note = form.cleaned_data.get("note")

            try:
                review_verification_document(
                    document=document,
                    reviewer=request.user,
                    accepted=accepted,
                    note=note,
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, _validation_error_text(exc))
            else:
                self.message_user(
                    request,
                    "Verification document review saved.",
                    level=messages.SUCCESS,
                )
                return redirect(
                    reverse(
                        "admin:organizations_organizationverificationdocument_change",
                        args=(document.pk,),
                    )
                )

        context = {
            **self.admin_site.each_context(request),
            "title": (
                "Document review — "
                f"{document.verification_case.organization}"
            ),
            "opts": self.model._meta,
            "original": document,
            "form": form,
            "document_open_url": self._secure_file_url(document),
            "document_download_url": self._secure_file_url(
                document,
                download=True,
            ),
            "media": self.media + form.media,
            "submit_label": "Save document review",
            "back_url": reverse(
                "admin:organizations_organizationverificationdocument_change",
                args=(document.pk,),
            ),
            "help_text": (
                "Rejecting a document requires a reviewer note. "
                "The case cannot be approved until every active document "
                "has been accepted."
            ),
        }

        return TemplateResponse(
            request,
            WORKFLOW_TEMPLATE,
            context,
        )

    @admin.action(description="Accept selected active verification documents")
    def accept_selected_documents(self, request, queryset):
        accepted_count = 0
        skipped = 0

        for document in queryset.select_related(
            "verification_case__organization"
        ):
            try:
                review_verification_document(
                    document=document,
                    reviewer=request.user,
                    accepted=True,
                )
            except (ValidationError, PermissionDenied):
                skipped += 1
            else:
                accepted_count += 1

        if accepted_count:
            self.message_user(
                request,
                f"Accepted {accepted_count} verification document(s).",
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} document(s) that could not be reviewed.",
                level=messages.WARNING,
            )


@admin.register(OrganizationVerificationGrant)
class OrganizationVerificationGrantAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "grant_type",
        "status_badge",
        "granted_by",
        "granted_at",
        "expires_at",
        "revoked_at",
        "workflow_button",
    )
    list_filter = (
        "grant_type",
        "status",
        "granted_at",
        "expires_at",
    )
    search_fields = (
        "organization__name",
        "organization__slug",
        "public_id",
        "verification_case__public_id",
        "granted_by__email",
    )
    list_select_related = (
        "organization",
        "verification_case",
        "relationship",
        "supersedes",
        "granted_by",
    )
    ordering = ("-granted_at", "-id")
    list_per_page = 50
    show_full_result_count = False
    date_hierarchy = "granted_at"

    readonly_fields = tuple(
        field.name
        for field in OrganizationVerificationGrant._meta.fields
    ) + ("workflow_actions",)

    fieldsets = (
        (
            "Grant",
            {
                "fields": (
                    "organization",
                    "public_id",
                    "grant_type",
                    "status",
                    "workflow_actions",
                    "granted_by",
                    "granted_at",
                    "expires_at",
                ),
            },
        ),
        (
            "Source",
            {
                "fields": (
                    "verification_case",
                    "relationship",
                    "supersedes",
                ),
            },
        ),
        (
            "Revocation",
            {
                "fields": (
                    "revoked_at",
                    "revocation_reason",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "active_slot",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            OrganizationVerificationGrantStatus.ACTIVE: "#198754",
            OrganizationVerificationGrantStatus.SUPERSEDED: "#6c757d",
            OrganizationVerificationGrantStatus.REVOKED: "#dc3545",
            OrganizationVerificationGrantStatus.EXPIRED: "#fd7e14",
        }

        return format_html(
            '<span style="display:inline-block;padding:2px 8px;'
            'border-radius:999px;background:{};color:#fff;font-weight:600;">'
            "{}</span>",
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    @admin.display(description="Workflow")
    def workflow_button(self, obj):
        if obj.status != OrganizationVerificationGrantStatus.ACTIVE:
            return "—"

        return format_html(
            '<a class="button" href="{}">Revoke</a>',
            self._workflow_url(obj),
        )

    @admin.display(description="Workflow actions")
    def workflow_actions(self, obj):
        if not obj:
            return "—"

        if obj.status != OrganizationVerificationGrantStatus.ACTIVE:
            return "Only an active grant can be revoked."

        return format_html(
            '<a class="button" href="{}">Revoke verification grant</a>',
            self._workflow_url(obj),
        )

    def _workflow_url(self, obj):
        return reverse(
            "admin:organizations_organizationverificationgrant_workflow",
            args=(obj.pk,),
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/workflow/",
                self.admin_site.admin_view(self.workflow_view),
                name="organizations_organizationverificationgrant_workflow",
            ),
        ]
        return custom_urls + urls

    def workflow_view(self, request, object_id):
        grant = self.get_object(request, object_id)

        if grant is None:
            raise Http404("Verification grant not found.")

        if not self.has_change_permission(request, grant):
            raise PermissionDenied

        form = VerificationGrantRevokeForm(
            request.POST or None,
            grant=grant,
        )

        if request.method == "POST" and form.is_valid():
            try:
                revoke_verification_grant(
                    grant=grant,
                    reviewer=request.user,
                    reason=form.cleaned_data["reason"],
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, _validation_error_text(exc))
            else:
                self.message_user(
                    request,
                    "Organization verification grant revoked.",
                    level=messages.SUCCESS,
                )
                return redirect(
                    reverse(
                        "admin:organizations_organizationverificationgrant_change",
                        args=(grant.pk,),
                    )
                )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Revoke verification — {grant.organization}",
            "opts": self.model._meta,
            "original": grant,
            "form": form,
            "media": self.media + form.media,
            "submit_label": "Revoke verification grant",
            "back_url": reverse(
                "admin:organizations_organizationverificationgrant_change",
                args=(grant.pk,),
            ),
            "help_text": (
                "Revoking a verification grant is audited and also revokes "
                "dependent sponsored-branch verification grants."
            ),
        }

        return TemplateResponse(
            request,
            WORKFLOW_TEMPLATE,
            context,
        )
