from django.contrib import admin
from .models import TermsAndPolicy, FAQ, SiteAnnouncement, UserFeedback, UserActionLog



# TERMS AND POLICY Admin -----------------------------------------------------------------------------------------
@admin.register(TermsAndPolicy)
class TermsAndPolicyAdmin(admin.ModelAdmin):
    list_display = ('title', 'policy_type', 'slug', 'last_updated', 'is_active')
    search_fields = ('title', 'policy_type', 'slug')
    list_filter = ('is_active', 'last_updated')
    ordering = ('-last_updated',)



# FAQ Admin ------------------------------------------------------------------------------------------------------
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'last_updated', 'is_active')
    search_fields = ('question',)
    list_filter = ('is_active', 'last_updated')
    ordering = ('-last_updated',)


# SITE ANNOUNCEMENT Admin -----------------------------------------------------------------------------------------
@admin.register(SiteAnnouncement)
class SiteAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'publish_date', 'is_active')
    search_fields = ('title',)
    list_filter = ('is_active', 'publish_date')
    ordering = ('-publish_date',)


# USER FEEDBACK Admin ---------------------------------------------------------------------------------------------
@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'created_at')
    search_fields = ('user__username', 'title')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


# USER ACTION LOG Admin --------------------------------------------------------------------------------------------
@admin.register(UserActionLog)
class UserActionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'content_type', 'object_id', 'action_timestamp')
    search_fields = ('user__username', 'action_type')
    list_filter = ('action_type', 'action_timestamp')
    ordering = ('-action_timestamp',)