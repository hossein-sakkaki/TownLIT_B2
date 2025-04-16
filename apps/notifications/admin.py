from django.contrib import admin
from .models import Notification, UserNotificationPreference


# Admin for UserNotificationPreference -------------------------------------------------
@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'enabled']
    list_filter = ['enabled', 'notification_type']
    search_fields = ['user__username']
    ordering = ['user', 'notification_type']
    list_editable = ['enabled']
    
    
# Admin for Notification ----------------------------------------------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'notification_type', 'created_at', 'is_read']
    list_filter = ['is_read', 'notification_type', 'created_at']
    search_fields = ['user__username', 'message']
    ordering = ['-created_at']
    list_editable = ['is_read']
    readonly_fields = ['created_at', 'content_type', 'object_id', 'content_object']
    fieldsets = [
        (None, {
            'fields': ['user', 'message', 'notification_type', 'is_read']
        }),
        ('Content Information', {
            'fields': ['content_type', 'object_id', 'content_object', 'link'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at'],
            'classes': ['collapse']
        }),
    ]