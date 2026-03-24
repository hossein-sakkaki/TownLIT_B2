# apps/profiles/admin/member.py

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from apps.profiles.admin_forms import MemberAdminForm
from apps.accounts.services.townlit_engine import get_member_townlit_state
from apps.accounts.services.townlit_verification_service import (
    admin_mark_townlit_verified,
    admin_revoke_townlit_verified,
)
from apps.profiles.models.member import Member


# Member Admin ----------------------------------------------------------------
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # Use custom form that validates and filters family by branch
    form = MemberAdminForm

    # --- Columns in changelist ---
    list_display = [
        'id',
        'user',
        'denomination_branch',
        'denomination_family',
        'spiritual_rebirth_day',
        'is_migrated',
        'is_active',
        'is_privacy',
        'register_date',

        'is_townlit_verified',
        'townlit_verified_at',
        'townlit_progress_score',
        'townlit_hard_requirements_ready_display',

        'is_hidden_by_confidants',
        'show_fellowship_in_profile',
        'hide_confidants',
    ]

    # --- Filters on right side ---
    list_filter = [
        'denomination_branch',
        'denomination_family',
        'is_migrated',
        'is_active',
        'is_privacy',
        'register_date',
        'is_townlit_verified',
    ]

    # --- Search fields ---
    search_fields = [
        'user__username',
        'user__email',
        'biography',
        'vision',
        'service_types__service__name',
        'denomination_branch',
        'denomination_family',
    ]

    autocomplete_fields = ['user']
    filter_horizontal = ['service_types', 'organization_memberships']

    readonly_fields = (
        'register_date',
        'is_townlit_verified',
        'townlit_verified_at',
        'townlit_verified_reason',
        'preview_townlit_score',
        'preview_townlit_missing_requirements',
        'preview_townlit_hard_requirements_ready',
        'preview_townlit_score_ready',
        'preview_townlit_identity_verified',
    )

    actions = [
        'mark_townlit_verified',
        'revoke_townlit_verified',
    ]

    # --- Fieldsets for edit page ---
    fieldsets = (
        ('Personal Info', {
            'fields': (
                'user',
                'biography',
                'vision',
                'spiritual_rebirth_day',
                'denomination_branch',
                'denomination_family',
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
                'is_hidden_by_confidants',
            )
        }),
        ('TownLIT Gold Status', {
            'fields': (
                'is_townlit_verified',
                'townlit_verified_at',
                'townlit_verified_reason',
            )
        }),
        ('TownLIT Gold Eligibility Preview', {
            'classes': ('collapse',),
            'fields': (
                'preview_townlit_identity_verified',
                'preview_townlit_score',
                'preview_townlit_hard_requirements_ready',
                'preview_townlit_score_ready',
                'preview_townlit_missing_requirements',
            )
        }),
        ('Dates', {'fields': ('register_date',)}),
    )

    def get_form(self, request, obj=None, **kwargs):
        # Keep reference if needed by other admin hooks
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Protect TownLIT Gold status fields from direct manual editing
        through the admin form.

        Grant/revoke must go through service-layer actions so audit/grant
        records stay consistent.
        """
        if change:
            original = type(obj).objects.get(pk=obj.pk)

            obj.is_townlit_verified = original.is_townlit_verified
            obj.townlit_verified_at = original.townlit_verified_at
            obj.townlit_verified_reason = original.townlit_verified_reason

        super().save_model(request, obj, form, change)

    def managed_organizations_display(self, obj):
        # Optional helper column if you want to add it to list_display
        return ', '.join([org.org_name for org in obj.managed_organizations()])
    managed_organizations_display.short_description = 'Managed Organizations'

    # -----------------------------
    # TownLIT preview helpers
    # -----------------------------
    def _get_townlit_state(self, obj):
        return get_member_townlit_state(obj)

    def townlit_progress_score(self, obj):
        state = self._get_townlit_state(obj)
        return f"{state['score']} / {state['threshold']}"
    townlit_progress_score.short_description = 'TownLIT Score'

    def townlit_hard_requirements_ready_display(self, obj):
        state = self._get_townlit_state(obj)
        return state['hard_requirements_ready']
    townlit_hard_requirements_ready_display.boolean = True
    townlit_hard_requirements_ready_display.short_description = 'Gold Hard Ready'

    def preview_townlit_identity_verified(self, obj):
        state = self._get_townlit_state(obj)
        return state['identity_verified']
    preview_townlit_identity_verified.boolean = True
    preview_townlit_identity_verified.short_description = 'Blue Identity Verified'

    def preview_townlit_score(self, obj):
        state = self._get_townlit_state(obj)
        return f"{state['score']} / {state['threshold']}"
    preview_townlit_score.short_description = 'TownLIT Score'

    def preview_townlit_hard_requirements_ready(self, obj):
        state = self._get_townlit_state(obj)
        return state['hard_requirements_ready']
    preview_townlit_hard_requirements_ready.boolean = True
    preview_townlit_hard_requirements_ready.short_description = 'Hard Requirements Ready'

    def preview_townlit_score_ready(self, obj):
        state = self._get_townlit_state(obj)
        return state['score_ready']
    preview_townlit_score_ready.boolean = True
    preview_townlit_score_ready.short_description = 'Score Ready'

    def preview_townlit_missing_requirements(self, obj):
        state = self._get_townlit_state(obj)
        return ", ".join(state['missing_requirements']) or "None"
    preview_townlit_missing_requirements.short_description = 'Missing Requirements'

    # -----------------------------
    # Admin actions
    # -----------------------------
    @admin.action(description="Mark as TownLIT GOLD verified")
    def mark_townlit_verified(self, request, queryset):
        success_count = 0

        for member in queryset.select_related("user"):
            try:
                admin_mark_townlit_verified(
                    actor=request.user,
                    target_member=member,
                    reason="Admin manually granted TownLIT Gold",
                )
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to grant TownLIT Gold for {member.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} member(s) marked as TownLIT Gold verified.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Revoke TownLIT GOLD verified")
    def revoke_townlit_verified(self, request, queryset):
        success_count = 0

        for member in queryset.select_related("user"):
            try:
                admin_revoke_townlit_verified(
                    actor=request.user,
                    target_member=member,
                    reason="Admin revoked TownLIT Gold",
                )
                success_count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Failed to revoke TownLIT Gold for {member.user}: {exc}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"{success_count} member(s) had TownLIT Gold revoked.",
                level=messages.SUCCESS,
            )
