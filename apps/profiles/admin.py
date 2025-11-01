from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils import timezone
from pathlib import Path


from common.aws.s3_utils import get_file_url
from apps.posts.models import Moment, Pray
from apps.profiles.admin_forms import MemberServiceTypeAdminForm, MemberAdminForm
from .models import (
                AcademicRecord,
                Friendship, MigrationHistory,
                GuestUser,
                Member, MemberServiceType,
                Client, ClientRequest,
                Customer,
                SpiritualGift, SpiritualGiftSurveyQuestion,
                SpiritualGiftSurveyResponse, MemberSpiritualGifts,
                SpiritualService
            )
from apps.profilesOrg.models import OrganizationManager

# Friendship Admin ---------------------------------------------------------------------
@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('initiator', 'friend', 'created_at', 'deleted_at', 'status_display', 'is_active')
    list_filter = ('created_at', 'status', 'deleted_at')
    search_fields = ('from_user__username', 'to_user__username')
    autocomplete_fields = ('from_user', 'to_user')
    readonly_fields = ('created_at',)
    ordering = ['-created_at']

    def initiator(self, obj):
        return obj.from_user.username

    def friend(self, obj):
        return obj.to_user.username

    def status_display(self, obj):
        color_map = {
            'pending': 'orange',
            'accepted': 'green',
            'declined': 'red',
            'pending_deletion': 'grey'
        }
        return format_html("<span style='color: {};'>{}</span>", color_map.get(obj.status, 'black'), obj.status.capitalize())

    initiator.admin_order_field = 'from_user__username'
    friend.admin_order_field = 'to_user__username'
    status_display.short_description = 'Status'


# Education Models Admin -----------------------------------------------------------------
class AcademicRecordInline(admin.TabularInline):
    model = AcademicRecord
    extra = 1
    fields = [
        'education_document_type', 'education_degree', 'school', 'country',
        'status', 'started_at', 'expected_graduation_at', 'graduated_at',
        'document', 'is_theology_related',
    ]
    readonly_fields = ['document']
    show_change_link = True


# AcademicRecord Admin --------------------------------------------------------------------
@admin.register(AcademicRecord)
class AcademicRecordAdmin(admin.ModelAdmin):
    list_display = [
        'education_document_type', 'education_degree', 'school', 'country',
        'status', 'period_display', 'is_theology_related'
    ]
    list_filter = [
        'education_degree', 'country', 'status', 'is_theology_related'
    ]
    search_fields = ['school', 'country', 'education_degree']
    readonly_fields = ['document']
    ordering = ['-started_at', '-graduated_at', '-expected_graduation_at', '-id']


# MIGRATION HISTORY Admin ------------------------------------------------------------
class MigrationHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'migration_type', 'migration_date')
    search_fields = ('user__username', 'migration_type')
    list_filter = ('migration_type', 'migration_date')

admin.site.register(MigrationHistory, MigrationHistoryAdmin)



# Organization Manager Inline
class OrganizationManagerInMemberInline(admin.TabularInline):
    model = OrganizationManager
    extra = 1

# MOMENT Admin Inline
class MomentInline(GenericTabularInline):
    model = Moment
    extra = 0
    readonly_fields = ['content', 'published_at']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(content_type=ContentType.objects.get_for_model(Member))

# PRAY Admin Inline
class PrayInline(GenericTabularInline):
    model = Pray
    extra = 0
    readonly_fields = ['title', 'content', 'published_at']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(content_type=ContentType.objects.get_for_model(Member))


# Member Admin
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # Use custom form that validates and filters family by branch
    form = MemberAdminForm

    # --- Columns in changelist ---
    list_display = [
        'user',
        'denomination_branch',        # ← NEW
        'denomination_family',        # ← NEW
        'spiritual_rebirth_day',
        'is_migrated',
        'is_active',
        'is_privacy',
        'register_date',
        'identity_verification_status',
        'is_verified_identity',
        'is_sanctuary_participant',
        'is_hidden_by_confidants',
        'show_fellowship_in_profile',
        'hide_confidants',
    ]

    # --- Filters on right side ---
    list_filter = [
        'denomination_branch',        # ← NEW
        'denomination_family',        # ← NEW
        'is_migrated',
        'is_active',
        'is_privacy',
        'register_date',
        'identity_verification_status',
        'is_verified_identity',
        'is_sanctuary_participant',
    ]

    # --- Search fields ---
    search_fields = [
        'user__username',
        'biography',
        'vision',
        'service_types__service__name',
        'denomination_branch',        # ← helpful for quick find
        'denomination_family',
    ]

    autocomplete_fields = ['user']
    filter_horizontal = ['service_types', 'organization_memberships']

    # --- Fieldsets for edit page ---
    fieldsets = (
        ('Personal Info', {
            'fields': (
                'user',
                'biography',
                'vision',
                'spiritual_rebirth_day',
                # Old field removed: 'denominations_type'
                'denomination_branch',       # ← NEW (required)
                'denomination_family',       # ← NEW (optional)
                'show_gifts_in_profile',
                'show_fellowship_in_profile',
                'hide_confidants',
            )
        }),
        ('Services', {'fields': ('service_types', 'academic_record')}),
        ('Organizations & Memberships', {'fields': ('organization_memberships',)}),
        ('Status', {
            'fields': (
                'is_migrated',
                'is_active',
                'is_privacy',
                'identity_verification_status',
                'identity_verified_at',
                'is_verified_identity',
                'is_sanctuary_participant',
                'is_hidden_by_confidants',
            )
        }),
        ('Dates', {'fields': ('register_date',)}),
    )

    # If you still need inlines, keep them (sample from your code)
    # inlines = [OrganizationManagerInMemberInline]
    # Example you had:
    # inlines = [MomentInline, PrayInline]

    def get_form(self, request, obj=None, **kwargs):
        # Keep reference if needed by other admin hooks
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)

    def managed_organizations_display(self, obj):
        # Optional helper column if you want to add it to list_display
        return ', '.join([org.org_name for org in obj.managed_organizations()])
    managed_organizations_display.short_description = 'Managed Organizations'


# GUESTUSER MOMENT Admin Inline
class GuestUserMomentInline(GenericTabularInline):
    model = Moment
    extra = 0
    readonly_fields = ['content', 'published_at']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(content_type=ContentType.objects.get_for_model(GuestUser))
    
    
# GUEST USER ADMIN Manager -----------------------------------------------------------
@admin.register(GuestUser)
class GuestUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'register_date', 'is_migrated', 'is_active']
    list_filter = ['is_migrated', 'is_active', 'register_date']
    search_fields = ['user__username']
    ordering = ['register_date', 'is_migrated', 'is_active']
    fieldsets = (
        ('User Info', {'fields': ('user',)}),
        ('Status', {'fields': ('is_migrated', 'is_active')}),
        ('Dates', {'fields': ('register_date',)}),
    )
    inlines = [GuestUserMomentInline]


# CUSTOMER ADMIN Manager -----------------------------------------------------------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'customer_phone_number', 'billing_address', 'get_shipping_addresses', 'register_date', 'is_active']
    list_filter = ['is_active', 'register_date', 'deactivation_reason']
    search_fields = ['user__username', 'customer_phone_number']

    fieldsets = (
        ('Customer Info', {'fields': ('user', 'customer_phone_number', 'billing_address', 'shipping_addresses')}),
        ('Status', {'fields': ('is_active', 'deactivation_reason', 'deactivation_note')}),
        ('Dates', {'fields': ('register_date',)}),
    )

    autocomplete_fields = ['billing_address', 'shipping_addresses']

    def get_shipping_addresses(self, obj):
        return ", ".join([str(address) for address in obj.shipping_addresses.all()])
    get_shipping_addresses.short_description = 'Shipping Addresses'

    

# CLIENT ADMIN Manager -----------------------------------------------------------
# Request
@admin.register(ClientRequest)
class ClientRequestAdmin(admin.ModelAdmin):
    list_display = ['request', 'description', 'register_date', 'is_active']
    list_filter = ['is_active', 'register_date']
    search_fields = ['request', 'description']
    
    fieldsets = (
        ('Request Info', {'fields': ('request', 'description', 'document_1', 'document_2')}),
        ('Status', {'fields': ('is_active',)}),
        ('Dates', {'fields': ('register_date',)}),
    )

# Client Admin
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['user', 'request', 'register_date', 'is_active']
    list_filter = ['is_active', 'register_date']
    search_fields = ['user__username', 'request__request']
    
    fieldsets = (
        ('Client Info', {'fields': ('user', 'organization_clients', 'request')}),
        ('Status', {'fields': ('is_active',)}),
        ('Dates', {'fields': ('register_date',)}),
    )
    
    filter_horizontal = ['organization_clients']
    autocomplete_fields = ['request']


# Gift Admin ----------------------------------------------------------------------
@admin.register(SpiritualGift)
class SpiritualGiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)

@admin.register(SpiritualGiftSurveyQuestion)
class SpiritualGiftSurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'question_number', 'language', 'gift')
    search_fields = ('question_text', 'question_number', 'language',)
    list_filter = ('language', 'gift')
    ordering = ('gift',)

@admin.register(SpiritualGiftSurveyResponse)
class SpiritualGiftSurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('member', 'question', 'answer')
    # search_fields = ('member__username', 'question__question_text',)
    search_fields = ('member__user__username', 'question__question_text',)
    list_filter = ('question',)
    ordering = ('member',)

@admin.register(MemberSpiritualGifts)
class MemberSpiritualGiftsAdmin(admin.ModelAdmin):
    list_display = ('member', 'get_gifts', 'survey_results')
    search_fields = ('member__user__username',)
    # search_fields = ('member__username',)
    list_filter = ('member',)
    ordering = ('member',)

    def get_gifts(self, obj):
        return ", ".join([gift.name for gift in obj.gifts.all()])
    get_gifts.short_description = _('Spiritual Gifts')





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

        # اگر وضعیت تازه است یا تغییر کرده:
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