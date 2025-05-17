from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    TermsAndPolicy, PolicyChangeHistory, FAQ, SiteAnnouncement, UserFeedback, UserActionLog, Prayer,
    VideoCategory, VideoSeries, OfficialVideo, VideoViewLog
)


# TERMS AND POLICY Admin -----------------------------------------------------------------------------------------
@admin.register(TermsAndPolicy)
class TermsAndPolicyAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }

    list_display = [
        'title', 'policy_type', 'language', 'version_number', 
        'display_location', 'footer_column', 'requires_acceptance', 
        'slug', 'last_updated', 'is_active'
    ]

    list_editable = [
        'language', 'version_number', 'display_location',
        'footer_column', 'requires_acceptance', 'is_active'
    ]

    list_filter = [
        'is_active', 'display_location', 'requires_acceptance',
        'language', 'last_updated'
    ]

    search_fields = ['title', 'policy_type', 'slug', 'version_number']
    ordering = ['-last_updated']
    readonly_fields = ['last_updated', 'slug']

    fieldsets = (
        ("Basic Info", {
            'fields': ('title', 'policy_type', 'slug', 'version_number', 'language')
        }),
        ("Display Settings", {
            'fields': ('display_location', 'footer_column', 'requires_acceptance', 'is_active')
        }),
        ("Content", {
            'fields': ('content',)
        }),
        ("Metadata", {
            'fields': ('last_updated',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


# Policy Change History Admin Admin -----------------------------------------------------------------------------
@admin.register(PolicyChangeHistory)
class PolicyChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ['policy', 'changed_at']
    list_filter = ['changed_at']
    search_fields = ['policy__title']
    readonly_fields = ['policy', 'old_content', 'changed_at']


# FAQ Admin ------------------------------------------------------------------------------------------------------
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = ('question', 'last_updated', 'is_active')
    search_fields = ('question',)
    list_filter = ('is_active', 'last_updated')
    ordering = ('-last_updated',)


# SITE ANNOUNCEMENT Admin -----------------------------------------------------------------------------------------
@admin.register(SiteAnnouncement)
class SiteAnnouncementAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = ('title', 'publish_date', 'is_active')
    search_fields = ('title',)
    list_filter = ('is_active', 'publish_date')
    ordering = ('-publish_date',)


# USER FEEDBACK Admin ---------------------------------------------------------------------------------------------
@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = ['id', 'user', 'title', 'status', 'created_at', 'has_screenshot']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'title', 'content']
    readonly_fields = ['user', 'title', 'content', 'screenshot_preview', 'created_at']
    list_per_page = 25
    ordering = ['-created_at']
    actions = ['mark_as_reviewed', 'mark_as_resolved']

    def has_screenshot(self, obj):
        return bool(obj.screenshot)
    has_screenshot.boolean = True
    has_screenshot.short_description = 'Screenshot?'

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<a href="{url}" target="_blank">'
                '<img src="{url}" width="200" style="border:1px solid #ccc; border-radius:6px;" />'
                '</a>',
                url=obj.screenshot.url
            )
        return "No screenshot"
    screenshot_preview.short_description = "Screenshot Preview"

    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(status='reviewed')
        self.message_user(request, f"{updated} feedback(s) marked as reviewed.")
    mark_as_reviewed.short_description = "Mark selected as Reviewed"

    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='resolved')
        self.message_user(request, f"{updated} feedback(s) marked as resolved.")
    mark_as_resolved.short_description = "Mark selected as Resolved"



# USER ACTION LOG Admin --------------------------------------------------------------------------------------------    
@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'content_type', 'object_id', 'action_timestamp')
    search_fields = ('user__username', 'action_type')
    list_filter = ('action_type', 'action_timestamp')
    ordering = ('-action_timestamp',)
    
    
# PRAYER Admin -----------------------------------------------------------------------------------------------
@admin.register(Prayer)
class PrayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'display_name', 'submitted_at', 'allow_display', 'is_active', 'has_response')
    list_filter = ('is_active', 'allow_display', 'responded_by')
    search_fields = ('full_name', 'email', 'content', 'admin_response')

    readonly_fields = ('user', 'responded_by', 'responded_at', 'submitted_at')

    fieldsets = (
        (None, {
            'fields': ('user', 'full_name', 'email', 'content', 'allow_display', 'is_active', 'submitted_at')
        }),
        ("Admin Response", {
            'fields': ('admin_response', 'responded_by', 'responded_at'),
        }),
    )

    def display_name(self, obj):
        if obj.user:
            return f"{obj.user.name} {obj.user.family}".strip() or obj.user.username
        return obj.full_name or "Guest"


    def save_model(self, request, obj, form, change):
        if obj.admin_response and not obj.responded_by:
            obj.responded_by = request.user
            obj.responded_at = timezone.now()
        super().save_model(request, obj, form, change)


# Video Category Admin --------------------------------------------------------------------------------------------
@admin.action(description="Mark selected videos as Active")
def make_active(self, request, queryset):
    queryset.update(is_active=True)

@admin.action(description="Mark selected videos as Inactive")
def make_inactive(self, request, queryset):
    queryset.update(is_active=False)
    
class OfficialVideoInline(admin.TabularInline):
    model = OfficialVideo
    fields = ("thumbnail", "title", "language", "episode_number", "is_active")
    readonly_fields = ("thumbnail",)
    extra = 5

    def thumbnail(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="80" height="auto" style="border-radius:4px;" />', obj.thumbnail.url)
        return "-"
    thumbnail.short_description = "Thumbnail"
    
@admin.register(VideoCategory)
class VideoCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(VideoSeries)
class VideoSeriesAdmin(admin.ModelAdmin):
    list_display = ("title", "language", "is_active", "created_at")
    list_filter = ("language", "is_active")
    search_fields = ("title", "description")
    ordering = ("-created_at",)
    inlines = [OfficialVideoInline]
    autocomplete_fields = ["intro_video"]



        
@admin.register(OfficialVideo)
class OfficialVideoAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail_preview", "view_link",
        "title", "language", "category", "series",
        "episode_number", "view_count", "is_active", "publish_date"
    )
    list_editable = ("is_active", "episode_number")
    list_filter = ("language", "category", "series", "is_active")
    search_fields = ("title", "description", "slug")
    ordering = ("-publish_date", "episode_number")
    readonly_fields = ("view_count", "created_at")
    autocomplete_fields = ("category", "series")
    prepopulated_fields = {"slug": ("title",)}
    actions = ['make_active', 'make_inactive']
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="100" height="auto" style="border-radius:6px;" />', obj.thumbnail.url)
        return "-"
    thumbnail_preview.short_description = "Thumbnail"

    def view_link(self, obj):
        if obj.slug:
            return format_html('<a href="/official/videos/{}/" target="_blank">View</a>', obj.slug)
        return "-"
    view_link.short_description = "View"



@admin.register(VideoViewLog)
class VideoViewLogAdmin(admin.ModelAdmin):
    list_display = ("video", "ip_address", "user_agent", "viewed_at")
    list_filter = ("viewed_at",)
    search_fields = ("video__title", "ip_address", "user_agent")
    ordering = ("-viewed_at",)