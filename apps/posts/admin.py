from django.contrib import admin
from .models import (
                Reaction, Comment, Resource, ServiceEvent,
                Testimony, Witness, Moment, Pray, Announcement, Lesson, Preach, Worship, MediaContent,
                Library, Mission, Conference, FutureConference 
            )



# Admin mixin for common methods -----------------------------------------------------------------
class MarkActiveMixin:
    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Selected items have been marked as inactive.")
    make_inactive.short_description = "Mark selected items as inactive"

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Selected items have been marked as active.")
    make_active.short_description = "Mark selected items as active"


# Reactions Admin ---------------------------------------------------------------------------------
@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('name', 'reaction_type', 'content_type', 'object_id', 'timestamp')
    search_fields = ('name__username', 'reaction_type')
    list_filter = ('reaction_type', 'timestamp', 'content_type')
    
    
# Comment Admin ------------------------------------------------------------------------------------
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['name', 'comment_summary', 'content_object', 'recomment_summary', 'published_at', 'is_active']
    list_filter = ['is_active', 'published_at', 'content_type']
    search_fields = ['name__username', 'comment', 'recomment__comment']
    date_hierarchy = 'published_at'
    
    def comment_summary(self, obj):
        return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
    comment_summary.short_description = 'Comment'

    def recomment_summary(self, obj):
        if obj.recomment:
            return obj.recomment.comment[:50] + "..." if len(obj.recomment.comment) > 50 else obj.recomment.comment
        return "No Recomment"
    recomment_summary.short_description = 'Recomment'
    
    # Display the content object related to the comment (e.g., Moment or Testimony)
    def content_object(self, obj):
        """Displays the content object (Moment, Testimony, etc.) the comment is associated with."""
        return obj.content_object
    content_object.short_description = 'Related Object'
    
    
# Resource Admin -----------------------------------------------------------------------------------
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['resource_name', 'resource_type', 'author', 'uploaded_at', 'is_active']
    search_fields = ['resource_name', 'resource_type', 'author', 'license']
    list_filter = ['resource_type', 'uploaded_at', 'is_active']
    actions = ['make_inactive', 'make_active']
    date_hierarchy = 'uploaded_at'
    readonly_fields = ['uploaded_at']

    # Optimized queryset for related fields
    def get_queryset(self, request):
        """Optimize the queryset for the Resource model."""
        queryset = super().get_queryset(request)
        return queryset
    
    
# Service Event Admin ------------------------------------------------------------------------------
@admin.register(ServiceEvent)
class ServiceEventAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['custom_event_type', 'organization_type', 'event_type_display', 'event_date', 'start_time', 'is_active']
    list_filter = ['organization_type', 'event_method', 'recurring', 'is_active', 'is_hidden', 'is_restricted', 'event_date']
    search_fields = ['custom_event_type', 'organization_type', 'event_type', 'description']
    autocomplete_fields = ['location']
    actions = ['make_inactive', 'make_active']
    date_hierarchy = 'event_date'
    fieldsets = (
        ('Basic Info', {
            'fields': ('organization_type', 'event_type', 'custom_event_type', 'event_banner', 'description', 'contact_information')
        }),
        ('Event Details', {
            'fields': ('event_date', 'day_of_week', 'start_time', 'duration', 'additional_notes', 'recurring', 'frequency')
        }),
        ('Location and Method', {
            'fields': ('event_method', 'location', 'event_link')
        }),
        ('Registration', {
            'fields': ('registration_required', 'registration_link')
        }),
        ('Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )

    # Display custom event type or fallback to standard event type
    def event_type_display(self, obj):
        """Show the event type or custom event type if available."""
        return obj.custom_event_type if obj.custom_event_type else obj.event_type
    event_type_display.short_description = 'Event Type'

    # Optimized queryset for related fields
    def get_queryset(self, request):
        """Optimize the queryset to reduce database queries."""
        queryset = super().get_queryset(request)
        return queryset.select_related('location')


# Inline Witness --------------------------------------------------------------------------------------
# class WitnessInline(admin.TabularInline):
#     model = Witness
#     extra = 2
#     autocomplete_fields = ['testimony']
    



# Witness Admin ---------------------------------------------------------------------------------------------------
@admin.register(Witness)
class WitnessAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 're_published_at', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 're_published_at']
    search_fields = ['title', 'testimony__title']
    fieldsets = (
        ('Witness Details', {
            'fields': ('title', 'testimony', 're_published_at')
        }),
        ('Permissions & Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )
    filter_horizontal = ['testimony']
    actions = ['make_active', 'make_inactive']

    # Optimize the queryset
    def get_queryset(self, request):
        """Optimize the queryset for better performance."""
        queryset = super().get_queryset(request)
        return queryset.select_related('testimony')
    
    # Display a shortened version of the title if it's too long
    def title_summary(self, obj):
        """Displays a shortened version of the title."""
        return obj.title[:50] + "..." if len(obj.title) > 50 else obj.title
    title_summary.short_description = 'Title'


# Moment Admin --------------------------------------------------------------------------------------------------------------
@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['content_summary', 'published_at', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['content']
    filter_horizontal = ['org_tags', 'user_tags']
    fieldsets = (
        ('Moment Content', {
            'fields': ('content', 'moment_file')
        }),
        ('Tags', {
            'fields': ('org_tags', 'user_tags')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'updated_at', 'is_active', 'is_hidden', 'is_restricted')
        })
    )

    def content_summary(self, obj):
        """Display a short snippet of the moment content for better admin overview."""
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_summary.short_description = 'Moment Content'


# Pray Admin --------------------------------------------------------------------------------------------------------------@admin.register(Pray)
class PrayAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'is_accepted', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at', 'is_accepted']
    search_fields = ['title', 'content']
    fieldsets = (
        ('Pray Details', {
            'fields': ('title', 'content', 'image', 'parent')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'updated_at', 'is_accepted', 'is_rejected', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Announcement Admin ------------------------------------------------------------------------------------------------------
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'created_at', 'to_date', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'created_at', 'to_date']
    search_fields = ['title', 'description']
    fieldsets = (
        ('Announcement Details', {
            'fields': ('title', 'description', 'image', 'meeting_type', 'url_link', 'link_sticker_text', 'location')
        }),
        ('Dates', {
            'fields': ('created_at', 'to_date')
        }),
        ('Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )


# Lesson Admin ------------------------------------------------------------------------------------------------------------
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'view', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'description']
    filter_horizontal = ['in_town_teachers']
    fieldsets = (
        ('Lesson Details', {
            'fields': ('title', 'season', 'episode', 'description', 'image', 'audio', 'video', 'parent')
        }),
        ('Teachers', {
            'fields': ('in_town_teachers', 'out_town_teachers')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'record_date', 'view', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Preach Admin ------------------------------------------------------------------------------------------------------------
@admin.register(Preach)
class PreachAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'view', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'out_town_preacher']
    fieldsets = (
        ('Preach Details', {
            'fields': ('title', 'in_town_preacher', 'out_town_preacher', 'image', 'video')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'view', 'is_active', 'is_hidden', 'is_restricted')
        })
    )
    

# Worship Admin -----------------------------------------------------------------------------------------------------------
@admin.register(Worship)
class WorshipAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'view', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'sermon', 'hymn_lyrics']
    filter_horizontal = ['in_town_leaders', 'worship_resources']
    fieldsets = (
        ('Worship Details', {
            'fields': ('title', 'season', 'episode', 'sermon', 'hymn_lyrics', 'image', 'audio', 'video', 'parent')
        }),
        ('Leaders', {
            'fields': ('in_town_leaders', 'out_town_leaders')
        }),
        ('Resources', {
            'fields': ('worship_resources',)
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'view', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Media Content Admin -----------------------------------------------------------------------------------------------------
@admin.register(MediaContent)
class MediaContentAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'content_type', 'published_at', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'description']
    
    fieldsets = (
        ('Media Content Details', {
            'fields': ('content_type', 'title', 'description', 'file', 'link')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Library Admin -----------------------------------------------------------------------------------------------------------
@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['book_name', 'author', 'published_date', 'downloaded', 'is_upcoming', 'is_downloadable', 'is_active']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'is_upcoming', 'is_downloadable', 'genre_type', 'published_date']
    search_fields = ['book_name', 'author', 'publisher_name', 'language', 'translation_language', 'translator']
    readonly_fields = ['downloaded']
    actions = ['make_active', 'make_inactive']
    fieldsets = (
        ('Book Details', {
            'fields': ('book_name', 'author', 'publisher_name', 'language', 'translation_language', 'translator', 'genre_type', 'image', 'pdf_file')
        }),
        ('Licensing & Sale', {
            'fields': ('license_type', 'sale_status', 'license_document')
        }),
        ('Release Info', {
            'fields': ('is_upcoming', 'is_downloadable', 'has_print_version')
        }),
        ('Status & Dates', {
            'fields': ('published_date', 'downloaded', 'is_active', 'is_hidden', 'is_restricted')
        })
    )

    def comment_summary(self, obj):
        """Displays a shortened version of the comment."""
        if obj.comments.exists():
            first_comment = obj.comments.first()
            return first_comment.comment[:50] + "..." if len(first_comment.comment) > 50 else first_comment.comment
        return "No comments"
    comment_summary.short_description = 'Comment Summary'
    
    def get_queryset(self, request):
        """Optimized query for related fields."""
        queryset = super().get_queryset(request)
        return queryset


# Mission Admin -----------------------------------------------------------------------------------------------------------
@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['mission_name', 'start_date', 'end_date', 'is_ongoing', 'location', 'is_active']
    list_filter = ['is_ongoing', 'is_active', 'is_hidden', 'start_date', 'end_date', 'location']
    search_fields = ['mission_name', 'description', 'contact_persons__username']
    actions = ['make_active', 'make_inactive']
    fieldsets = (
        ('Mission Details', {
            'fields': ('mission_name', 'description', 'image_or_video', 'location', 'contact_persons', 'start_date', 'end_date', 'is_ongoing')
        }),
        ('Funding Information', {
            'fields': ('funding_goal', 'raised_funds', 'funding_link')
        }),
        ('Volunteer & Report', {
            'fields': ('volunteer_opportunities', 'mission_report')
        }),
        ('Permissions & Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )
    filter_horizontal = ['contact_persons']

    def comment_summary(self, obj):
        """Displays a shortened version of the comment."""
        if obj.comments.exists():
            first_comment = obj.comments.first()
            return first_comment.comment[:50] + "..." if len(first_comment.comment) > 50 else first_comment.comment
        return "No comments"
    comment_summary.short_description = 'Comment Summary'

    def get_queryset(self, request):
        """Optimize the queryset for better performance."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('contact_persons')


# Conference Admin -----------------------------------------------------------------------------------------------------------@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['conference_name', 'conference_date', 'conference_end_date', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'conference_date', 'conference_end_date']
    search_fields = ['conference_name', 'description']
    date_hierarchy = 'conference_date'
    filter_horizontal = ['workshops', 'conference_resources']
    readonly_fields = ['slug']
    actions = ['make_inactive', 'make_active']
    fieldsets = (
        ('Conference Info', {
            'fields': ('conference_name', 'description', 'slug')
        }),
        ('Workshops & Resources', {
            'fields': ('workshops', 'conference_resources')
        }),
        ('Dates & Status', {
            'fields': ('conference_date', 'conference_time', 'conference_end_date', 'is_active', 'is_hidden', 'is_restricted')
        }),
    )


# Future Conference Admin -----------------------------------------------------------------------------------------------------------
@admin.register(FutureConference)
class FutureConferenceAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['conference_name', 'conference_date', 'conference_end_date', 'registration_required', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'conference_date', 'conference_end_date', 'registration_required']
    search_fields = ['conference_name', 'conference_description']
    date_hierarchy = 'conference_date'
    filter_horizontal = ['in_town_speakers', 'sponsors']
    readonly_fields = ['slug']
    actions = ['make_inactive', 'make_active']
    fieldsets = (
        ('Conference Info', {
            'fields': ('conference_name', 'conference_description', 'slug')
        }),
        ('Speakers & Sponsors', {
            'fields': ('in_town_speakers', 'out_town_speakers', 'sponsors')
        }),
        ('Registration & Location', {
            'fields': ('registration_required', 'delivery_type', 'conference_location', 'registration_link')
        }),
        ('Dates & Status', {
            'fields': ('conference_date', 'conference_time', 'conference_end_date', 'is_active', 'is_hidden', 'is_restricted')
        }),
    )





# Testimony Admin ---------------------------------------------------------------------------------------------------------
# posts/admin.py

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

from .models import Testimony  # مسیر مدل خودت
# اگر M2Mها در اپ‌های دیگرند، برحسب نیاز import کن

@admin.register(Testimony)
class TestimonyAdmin(admin.ModelAdmin):
    """
    Admin focused on observability & troubleshooting of media conversion.
    """
    # -------- List view --------
    list_display = (
        "id",
        "slug",
        "type",
        "owner_repr",
        "is_active",
        "is_converted",
        "media_flags",
        "published_at",
        "updated_at",
    )
    list_filter = (
        "type",
        "is_active",
        "is_converted",
        "is_hidden",
        "is_restricted",
        "is_suspended",
        ("published_at", DateFieldListFilter),
        "content_type",    # lets you filter by owner model (Member, Organization, …)
    )
    search_fields = (
        "slug",
        "title",
        "content",
        "audio",
        "video",
        "thumbnail",
    )
    ordering = ("-id",)

    # Speed & UX for large M2M sets
    filter_horizontal = ("org_tags", "user_tags")
    raw_id_fields = ("user_tags", "org_tags")

    # Fields layout on detail
    readonly_fields = (
        "owner_link",
        "preview_media",
        "file_links",
        "diagnostics",
        # timestamps are usually readonly in admin
        "published_at",
        "updated_at",
    )

    fieldsets = (
        ("Basic", {
            "fields": (
                ("type", "title", "slug"),
                "content",
            )
        }),
        ("Owner (Generic)", {
            "fields": (
                ("content_type", "object_id"),
                "owner_link",
            )
        }),
        ("Media", {
            "fields": (
                "thumbnail",
                "audio",
                "video",
                "preview_media",
                "file_links",
            )
        }),
        ("Moderation & Visibility", {
            "fields": (
                ("is_active", "is_hidden", "is_restricted", "is_suspended"),
                "reports_count",
            )
        }),
        ("System", {
            "fields": (
                ("is_converted",),
                ("published_at", "updated_at"),
                "diagnostics",
            )
        }),
        ("Tags (optional)", {
            "classes": ("collapse",),
            "fields": ("org_tags", "user_tags"),
        }),
    )

    # -------- Computed columns / helpers --------
    def owner_repr(self, obj: Testimony):
        """Compact owner representation for the changelist."""
        try:
            return f"{obj.content_type.model}#{obj.object_id}"
        except Exception:
            return "-"

    owner_repr.short_description = "Owner"

    def owner_link(self, obj: Testimony):
        """Clickable link to owner object in admin (if available)."""
        try:
            ct: ContentType = obj.content_type
            url = reverse(f"admin:{ct.app_label}_{ct.model}_change", args=[obj.object_id])
            return mark_safe(f'<a href="{url}">{ct.app_label}.{ct.model} #{obj.object_id}</a>')
        except Exception:
            return "-"

    owner_link.short_description = "Owner link"

    def media_flags(self, obj: Testimony):
        """Quick flags: A/V/T presence."""
        a = "A✔" if getattr(obj, "audio") else "A–"
        v = "V✔" if getattr(obj, "video") else "V–"
        t = "T✔" if getattr(obj, "thumbnail") else "T–"
        return f"{a} {v} {t}"

    media_flags.short_description = "Media"

    def preview_media(self, obj: Testimony):
        """Inline preview (best-effort). HLS may only play natively on Safari."""
        parts = []
        try:
            if obj.thumbnail:
                parts.append(f'<div><img src="{obj.thumbnail.url}" alt="thumb" style="max-width:220px;height:auto;border:1px solid #ddd;padding:2px"/></div>')
        except Exception:
            pass

        try:
            if obj.audio:
                parts.append(f'''
                    <div style="margin-top:8px">
                      <audio controls preload="metadata" style="width:280px">
                        <source src="{obj.audio.url}"/>
                        Your browser does not support the audio element.
                      </audio>
                    </div>
                ''')
        except Exception:
            pass

        # HLS playback via <video src=master.m3u8> works natively on Safari; others may need hls.js
        try:
            if obj.video:
                parts.append(f'''
                    <div style="margin-top:8px">
                      <video controls preload="metadata" style="max-width:420px;height:auto">
                        <source src="{obj.video.url}" type="application/vnd.apple.mpegurl"/>
                        Your browser may not play HLS natively.
                      </video>
                    </div>
                ''')
        except Exception:
            pass

        return mark_safe("".join(parts) or "<em>No preview</em>")

    preview_media.short_description = "Preview"

    def file_links(self, obj: Testimony):
        """Direct links to storage paths (helpful for verifying S3 uploads)."""
        rows = []
        for label in ("thumbnail", "audio", "video"):
            f = getattr(obj, label, None)
            if f:
                try:
                    rows.append(f'<div><strong>{label}</strong>: <a href="{f.url}" target="_blank" rel="noopener">{f.name}</a></div>')
                except Exception:
                    rows.append(f'<div><strong>{label}</strong>: {getattr(f, "name", "-")}</div>')
            else:
                rows.append(f"<div><strong>{label}</strong>: <em>—</em></div>")
        return mark_safe("".join(rows))

    file_links.short_description = "File URLs"

    def diagnostics(self, obj: Testimony):
        """
        Quick consistency check: flags common causes of 'file on S3 but no DB/404' or conversion stalls.
        """
        issues = []

        # type/content coherence (mirrors model.clean)
        if obj.type == Testimony.TYPE_AUDIO:
            if not obj.audio:
                issues.append("Audio testimony has no audio file.")
            if obj.content:
                issues.append("Audio testimony should not have content.")
            if obj.video:
                issues.append("Audio testimony should not have video.")
        elif obj.type == Testimony.TYPE_VIDEO:
            if not obj.video:
                issues.append("Video testimony has no video file.")
            if obj.content:
                issues.append("Video testimony should not have content.")
            if obj.audio:
                issues.append("Video testimony should not have audio.")
        elif obj.type == Testimony.TYPE_WRITTEN:
            if not obj.content:
                issues.append("Written testimony requires content.")
            if obj.audio or obj.video:
                issues.append("Written testimony should not have audio/video.")

        # conversion hints
        try:
            if obj.type in (Testimony.TYPE_AUDIO, Testimony.TYPE_VIDEO):
                if not obj.is_converted:
                    issues.append("Media not converted yet (is_converted=False).")
                # if audio present and name already endswith .mp3 but is_converted False
                if obj.type == Testimony.TYPE_AUDIO and getattr(obj, "audio") and str(obj.audio.name).lower().endswith(".mp3") and not obj.is_converted:
                    issues.append("Audio is MP3 but is_converted=False (no-op case).")
        except Exception:
            pass

        # visibility
        if not obj.is_active:
            issues.append("Item is inactive.")
        if obj.is_hidden:
            issues.append("Item is hidden.")
        if obj.is_restricted:
            issues.append("Item is restricted.")
        if obj.is_suspended:
            issues.append("Item is suspended.")

        if not issues:
            return mark_safe('<span style="color:#0a0">No issues detected</span>')

        lis = "".join(f"<li>{admin.utils.escape(i)}</li>" for i in issues)
        return mark_safe(f'<ul style="margin:0;padding-left:16px;color:#a00">{lis}</ul>')

    diagnostics.short_description = "Diagnostics"

    # -------- Actions --------
    actions = ("action_mark_active", "action_mark_inactive", "action_requeue_conversion", "action_rebuild_slug")

    @admin.action(description="Mark selected as Active")
    def action_mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} item(s) marked active.")

    @admin.action(description="Mark selected as Inactive")
    def action_mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} item(s) marked inactive.")

    @admin.action(description="Requeue media conversion")
    def action_requeue_conversion(self, request, queryset):
        # Force reconversion and (re)enqueue tasks
        cnt = 0
        for obj in queryset:
            try:
                obj.is_converted = False
                obj.save(update_fields=["is_converted"])
                obj.convert_uploaded_media_async()  # from MediaConversionMixin
                cnt += 1
            except Exception as e:
                self.message_user(request, f"Failed to requeue for {obj.pk}: {e}", level="error")
        self.message_user(request, f"{cnt} item(s) requeued for conversion.")

    @admin.action(description="Rebuild slug (unique)")
    def action_rebuild_slug(self, request, queryset):
        """
        Useful if you suspect slug collision caused DB rollback:
        regenerates slug using SlugMixin logic by clearing and re-saving.
        """
        cnt = 0
        for obj in queryset:
            try:
                # Keep a stable source; SlugMixin will regenerate
                obj.slug = None
                obj.save(update_fields=["slug"])  # triggers SlugMixin.save
                cnt += 1
            except Exception as e:
                self.message_user(request, f"Failed to rebuild slug for {obj.pk}: {e}", level="error")
        self.message_user(request, f"{cnt} slug(s) rebuilt.")

    # -------- Search tweaks --------
    def get_search_results(self, request, queryset, search_term):
        """
        Extend default search to allow quick owner lookup by 'object_id' when the term is numeric.
        """
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term.isdigit():
            qs = qs | queryset.filter(object_id=int(search_term))
        return qs, use_distinct
