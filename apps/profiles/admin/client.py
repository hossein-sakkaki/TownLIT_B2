# apps/profiles/admin/client.py

from django.contrib import admin

from apps.profiles.models.client import Client, ClientRequest


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