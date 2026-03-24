# apps/profiles/admin/relationships.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.profiles.models.relationships import Friendship, Fellowship


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('id', 'initiator', 'friend', 'created_at', 'deleted_at', 'status_display', 'is_active')
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
            'pending_deletion': 'grey',
        }
        return format_html(
            "<span style='color: {};'>{}</span>",
            color_map.get(obj.status, 'black'),
            obj.status.capitalize(),
        )

    initiator.admin_order_field = 'from_user__username'
    friend.admin_order_field = 'to_user__username'
    status_display.short_description = 'Status'


@admin.register(Fellowship)
class FellowshipAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'from_user',
        'to_user',
        'fellowship_type',
        'reciprocal_fellowship_type',
        'status',
        'created_at',
        'updated_at',
    )

    list_filter = (
        'fellowship_type',
        'reciprocal_fellowship_type',
        'status',
        'created_at',
    )

    search_fields = (
        'from_user__username',
        'from_user__email',
        'to_user__username',
        'to_user__email',
    )

    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        (_('Fellowship Information'), {
            'fields': (
                'from_user',
                'to_user',
                'fellowship_type',
                'reciprocal_fellowship_type',
                'status',
            )
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def __str__(self, obj):
        return f"{obj.from_user} → {obj.to_user} ({obj.fellowship_type})"