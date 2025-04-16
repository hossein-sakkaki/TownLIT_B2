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
    
    
# Testimony Admin ---------------------------------------------------------------------------------------------------------
@admin.register(Testimony)
class TestimonyAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'content']
    filter_horizontal = ['org_tags', 'user_tags']
    
    fieldsets = (
        ('Testimony Details', {
            'fields': ('title', 'content', 'audio', 'video', 'thumbnail_1', 'thumbnail_2', 'org_tags', 'user_tags', 'content_type', 'object_id')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'updated_at', 'is_active', 'is_hidden', 'is_restricted')
        }),
    )
    # inlines = [WitnessInline]


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

