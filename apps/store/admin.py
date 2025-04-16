from django.contrib import admin
from django_admin_listfilter_dropdown.filters import DropdownFilter
from .models import ServiceCategory, Store
from apps.posts.admin import MarkActiveMixin

# SERVICE CATEGORY ADMIN Manager -----------------------------------------------------------
@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['category_name', 'description']
    search_fields = ['category_name']
    list_filter = ['category_name']
    ordering = ['category_name']

    def get_queryset(self, request):
        # Optimize the queryset for better performance
        queryset = super().get_queryset(request)
        return queryset

# STORE ADMIN Manager ---------------------------------------------------------------------
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['custom_service_name', 'organization', 'is_verified', 'is_active', 'register_date', 'revenue']
    list_filter = ['is_active', 'is_verified', 'is_restricted', 'currency_preference', 'register_date']
    search_fields = ['custom_service_name', 'organization__org_name', 'store_phone_number', 'license_number']
    filter_horizontal = ['service_categories', 'products']
    readonly_fields = ['register_date']
    actions = ['make_inactive', 'make_active']

    fieldsets = (
        ('Store Information', {
            'fields': ('organization', 'custom_service_name', 'description', 'store_logo', 'store_phone_number', 'store_address', 'service_categories')
        }),
        ('License and Tax', {
            'fields': ('license_number', 'license_expiry_date', 'tax_id', 'store_license')
        }),
        ('Financial Information', {
            'fields': ('revenue', 'sales_report')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_active', 'is_hidden', 'is_restricted')
        }),
        ('Dates', {
            'fields': ('register_date', 'active_date')
        }),
    )

    def get_queryset(self, request):
        # Optimize the queryset for better performance
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('organization', 'service_categories', 'products')

    
