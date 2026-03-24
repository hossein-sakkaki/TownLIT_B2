# apps/profiles/admin/academic.py

from django.contrib import admin

from apps.profiles.models.academic import AcademicRecord


class AcademicRecordInline(admin.TabularInline):
    model = AcademicRecord
    extra = 1
    fields = [
        'education_document_type', 'education_degree', 'school', 'country',
        'status', 'started_at', 'expected_graduation_at', 'graduated_at',
        'document', 'is_theology_related',
    ]
    readonly_fields = ['document']
    show_change_link = True


@admin.register(AcademicRecord)
class AcademicRecordAdmin(admin.ModelAdmin):
    list_display = [
        'education_document_type', 'education_degree', 'school', 'country',
        'status', 'period_display', 'is_theology_related',
    ]
    list_filter = [
        'education_degree', 'country', 'status', 'is_theology_related',
    ]
    search_fields = ['school', 'country', 'education_degree']
    readonly_fields = ['document']
    ordering = ['-started_at', '-graduated_at', '-expected_graduation_at', '-id']