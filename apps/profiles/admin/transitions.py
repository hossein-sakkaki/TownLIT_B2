# apps/profiles/admin/transitions.py

from django.contrib import admin

from apps.profiles.models.transitions import MigrationHistory


@admin.register(MigrationHistory)
class MigrationHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'migration_type', 'migration_date')
    search_fields = ('user__username', 'migration_type')
    list_filter = ('migration_type', 'migration_date')


