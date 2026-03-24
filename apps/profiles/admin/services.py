# apps/profiles/admin/services.py

from django.contrib import admin
from django.utils.html import format_html

from django.utils import timezone
from pathlib import Path
from django.utils.translation import gettext_lazy as _

from apps.profiles.models.member import Member
from apps.profiles.models.services import MemberServiceType
from common.aws.s3_utils import get_file_url
from apps.profiles.admin_forms import MemberServiceTypeAdminForm


# ----- Inline on Member (optional) ------------------------------------------------
class MemberServiceTypeInline(admin.TabularInline):
    # M2M through model between Member and MemberServiceType
    model = Member.service_types.through
    extra = 0
    verbose_name = "Service link"
    verbose_name_plural = "Linked services"
    can_delete = True


# ----- Small helpers --------------------------------------------------------------
def _owners_str(obj: MemberServiceType) -> str:
    owners = obj.member_service_types.all().select_related("user")[:5]
    names = []
    for m in owners:
        if m.user_id and hasattr(m.user, "get_full_name"):
            full = m.user.get_full_name() or ""
        else:
            full = ""
        uname = (m.user.username if (m.user_id and hasattr(m.user, "username")) else "") or ""
        names.append(full or uname or f"Member #{m.pk}")
    more = obj.member_service_types.count() - len(owners)
    return ", ".join(names) + (f" (+{more})" if more > 0 else "")


def _presigned_or_dash(obj: MemberServiceType) -> str:
    key = getattr(getattr(obj, "document", None), "name", None)
    if not key:
        return "—"
    url = get_file_url(key=key, default_url=None)
    if not url:
        return "—"
    return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">View</a>', url)


# ----- Admin Model ----------------------------------------------------------------
@admin.register(MemberServiceType)
class MemberServiceTypeAdmin(admin.ModelAdmin):
    form = MemberServiceTypeAdminForm

    # columns in changelist
    list_display = (
        "id",
        "service_name",
        "is_sensitive_flag",
        "status",
        "owners",
        "issued_at",
        "expires_at",
        "register_date",
        "document_link",
        "short_review_note",
        "is_active",
    )
    list_select_related = ("service",)

    # filters
    list_filter = (
        "status",
        "service__is_sensitive",
        "service",
        ("register_date", admin.DateFieldListFilter),
        ("issued_at", admin.DateFieldListFilter),
        ("expires_at", admin.DateFieldListFilter),
        "is_active",
    )

    # search
    search_fields = (
        "service__name",
        "service__description",
        "credential_issuer",
        "credential_number",
        "credential_url",
        "history",
        "member_service_types__user__username",
        "member_service_types__user__first_name",
        "member_service_types__user__last_name",
    )

    ordering = ("-register_date", "-id")

    # read-only fields (rendered via methods)
    readonly_fields = (
        "register_date",
        "reviewed_at",
        "reviewed_by",
        "verified_at",
        "document_name",
        "document_size",
        "document_preview",
    )

    # layout in change form
    fieldsets = (
        ("Service", {
            "fields": ("service", "history", "is_active"),
        }),
        ("Credential", {
            "fields": (
                "document", "document_preview", "document_name", "document_size",
                "credential_issuer", "credential_number", "credential_url",
                "issued_at", "expires_at",
            ),
        }),
        ("Moderation", {
            # status: pending / approved / rejected / active
            "fields": ("status", "review_note", "reviewed_at", "reviewed_by", "verified_at"),
        }),
    )

    # ----- list display helpers -----
    def service_name(self, obj):
        return getattr(obj.service, "name", "—")
    service_name.short_description = "Service"

    def is_sensitive_flag(self, obj):
        return bool(getattr(obj.service, "is_sensitive", False))
    is_sensitive_flag.boolean = True
    is_sensitive_flag.short_description = "Sensitive"

    def owners(self, obj):
        return _owners_str(obj)
    owners.short_description = "Owners"

    def document_link(self, obj):
        return _presigned_or_dash(obj)
    document_link.short_description = "Document"

    def short_review_note(self, obj):
        txt = (obj.review_note or "").strip()
        return (txt[:45] + "…") if len(txt) > 45 else (txt or "—")
    short_review_note.short_description = "Review note"

    # ----- readonly_fields renderers -----
    def document_preview(self, obj):
        return self.document_link(obj)
    document_preview.short_description = "Document (open)"

    def document_name(self, obj):
        key = getattr(getattr(obj, "document", None), "name", "")
        return Path(key).name if key else "—"
    document_name.short_description = "Document name"

    def document_size(self, obj):
        try:
            return obj.document.size if obj.document else "—"
        except Exception:
            return "—"
    document_size.short_description = "Document size (bytes)"

    # ----- bulk actions -----------------------------------------------------
    actions = ("approve_selected", "reject_selected", "reset_to_pending")

    @admin.action(description="Approve selected services")
    def approve_selected(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(
            status=MemberServiceType.Status.APPROVED,
            reviewed_at=now,
            reviewed_by=request.user,
            verified_at=now,
        )
        self.message_user(request, f"{updated} item(s) approved.")

    @admin.action(description="Reject selected services")
    def reject_selected(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(
            status=MemberServiceType.Status.REJECTED,
            reviewed_at=now,
            reviewed_by=request.user,
            verified_at=None,   # optional: clear verification on reject
        )
        self.message_user(request, f"{updated} item(s) rejected.")

    @admin.action(description="Reset selected to pending review")
    def reset_to_pending(self, request, queryset):
        # NOTE: we intentionally DO NOT clear review_note / reviewed_* to preserve prior context.
        updated = queryset.update(status=MemberServiceType.Status.PENDING)
        self.message_user(request, f"{updated} item(s) moved to pending.")
        
    # -------------------------------------------------------
    def save_model(self, request, obj, form, change):
        new_status = form.cleaned_data.get("status", obj.status)

        prev_status = None
        if change and obj.pk:
            try:
                prev_status = MemberServiceType.objects.only("status").get(pk=obj.pk).status
            except MemberServiceType.DoesNotExist:
                prev_status = None

        if not change or (prev_status != new_status):
            now = timezone.now()

            if new_status == MemberServiceType.Status.APPROVED:
                obj.reviewed_at = now
                obj.reviewed_by = request.user
                obj.verified_at = now

            elif new_status == MemberServiceType.Status.REJECTED:
                obj.reviewed_at = now
                obj.reviewed_by = request.user
                obj.verified_at = None

            elif new_status == MemberServiceType.Status.PENDING:
                pass

            elif new_status == MemberServiceType.Status.ACTIVE:
                pass

        super().save_model(request, obj, form, change)