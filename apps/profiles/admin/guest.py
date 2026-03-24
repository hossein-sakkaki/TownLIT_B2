# apps/profiles/admin/guest.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.profiles.models.guest import GuestUser


@admin.register(GuestUser)
class GuestUserAdmin(admin.ModelAdmin):
    """
    Admin for GuestUser profile.
    """

    list_display = (
        "id",
        "user_link",
        "username",
        "email",
        "biography_preview",
        "is_privacy",
        "is_migrated",
        "is_active",
        "register_date",
        "view_public_profile",
    )

    list_filter = (
        "is_privacy",
        "is_migrated",
        "is_active",
        "register_date",
        "user__is_active",
        "user__is_suspended",
        "user__is_deleted",
        "user__is_account_paused",
        "user__is_member",
    )

    search_fields = (
        "user__username",
        "user__email",
        "user__name",
        "user__family",
        "biography",
    )

    readonly_fields = (
        "id",
        "slug",
        "url_name",
        "register_date",
        "user_link",
        "public_profile_link",
        "created_user_status",
    )

    autocomplete_fields = ("user",)

    ordering = ("-register_date", "-id")

    list_select_related = ("user",)

    fieldsets = (
        (
            "Guest Profile",
            {
                "fields": (
                    "user",
                    "user_link",
                    "biography",
                    "is_privacy",
                    "is_migrated",
                    "is_active",
                )
            },
        ),
        (
            "System",
            {
                "fields": (
                    "id",
                    "slug",
                    "url_name",
                    "register_date",
                )
            },
        ),
        (
            "User Status",
            {
                "fields": (
                    "created_user_status",
                )
            },
        ),
        (
            "Links",
            {
                "fields": (
                    "public_profile_link",
                )
            },
        ),
    )

    def get_queryset(self, request):
        # Optimize user access
        qs = super().get_queryset(request)
        return qs.select_related("user")

    def username(self, obj):
        return getattr(obj.user, "username", "-")
    username.short_description = "Username"
    username.admin_order_field = "user__username"

    def email(self, obj):
        return getattr(obj.user, "email", "-")
    email.short_description = "Email"
    email.admin_order_field = "user__email"

    def biography_preview(self, obj):
        # Short bio preview
        if not obj.biography:
            return "-"
        if len(obj.biography) <= 60:
            return obj.biography
        return f"{obj.biography[:60]}..."
    biography_preview.short_description = "Biography"

    def user_link(self, obj):
        # Link to CustomUser admin
        if not obj.user_id:
            return "-"
        url = reverse("admin:accounts_customuser_change", args=[obj.user_id])
        label = obj.user.username or obj.user.email or f"User #{obj.user_id}"
        return format_html('<a href="{}">{}</a>', url, label)
    user_link.short_description = "User"

    def created_user_status(self, obj):
        # Compact user status summary
        user = obj.user
        bits = [
            f"is_active={user.is_active}",
            f"is_member={user.is_member}",
            f"is_suspended={user.is_suspended}",
            f"is_deleted={user.is_deleted}",
            f"is_account_paused={user.is_account_paused}",
        ]
        return ", ".join(bits)
    created_user_status.short_description = "Base User Status"

    def public_profile_link(self, obj):
        # API/public route helper
        if not obj.user_id or not obj.user.username:
            return "-"
        path = f"/api/v1/profiles/profile/{obj.user.username}/"
        return format_html('<a href="{}" target="_blank">{}</a>', path, path)
    public_profile_link.short_description = "Unified Public Profile"

    def view_public_profile(self, obj):
        # Quick open link
        if not obj.user_id or not obj.user.username:
            return "-"
        path = f"/api/v1/profiles/profile/{obj.user.username}/"
        return format_html('<a href="{}" target="_blank">Open</a>', path)
    view_public_profile.short_description = "Public Profile"

    actions = (
        "mark_active",
        "mark_inactive",
        "mark_private",
        "mark_public",
        "mark_migrated",
        "mark_not_migrated",
    )

    @admin.action(description="Mark selected guest profiles as active")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} guest profile(s) marked as active.")

    @admin.action(description="Mark selected guest profiles as inactive")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} guest profile(s) marked as inactive.")

    @admin.action(description="Mark selected guest profiles as private")
    def mark_private(self, request, queryset):
        updated = queryset.update(is_privacy=True)
        self.message_user(request, f"{updated} guest profile(s) marked as private.")

    @admin.action(description="Mark selected guest profiles as public")
    def mark_public(self, request, queryset):
        updated = queryset.update(is_privacy=False)
        self.message_user(request, f"{updated} guest profile(s) marked as public.")

    @admin.action(description="Mark selected guest profiles as migrated")
    def mark_migrated(self, request, queryset):
        updated = queryset.update(is_migrated=True)
        self.message_user(request, f"{updated} guest profile(s) marked as migrated.")

    @admin.action(description="Mark selected guest profiles as not migrated")
    def mark_not_migrated(self, request, queryset):
        updated = queryset.update(is_migrated=False)
        self.message_user(request, f"{updated} guest profile(s) marked as not migrated.")