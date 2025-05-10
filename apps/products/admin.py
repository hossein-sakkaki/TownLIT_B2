from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q, Count
from .models import Product, ProductGroup, Brand, Feature, FeatureValue, ProductFeature, Gallery



# PRODUCT GROUP ADMIN Manager -----------------------------------------------------------
class ProductGroupInline(admin.TabularInline):
    model = ProductGroup
    extra = 1

class GroupFilter(SimpleListFilter):
    title = 'Product Group'
    parameter_name = 'Group'

    def lookups(self, request, model_admin):
        sub_group = ProductGroup.objects.filter(~Q(group_parent=None))
        groups = set([item.group_parent for item in sub_group])
        return [(item.id, item.group_title) for item in groups]

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(Q(group_parent=self.value()))
        return queryset

@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ['group_title', 'group_parent', 'published_date', 'is_active', 'count_sub_group']
    list_editable = ['is_active']
    search_fields = ['group_title', 'slug']
    ordering = ['is_active', 'group_parent']
    list_filter = ('group_parent',)

    inlines = [ProductGroupInline]

    def get_queryset(self, *args, **kwargs):
        qs = super(ProductGroupAdmin, self).get_queryset(*args, **kwargs)
        qs = qs.annotate(sub_group=Count('groups'))
        return qs

    def count_sub_group(self, obj):
        return obj.sub_group


# BRAND ADMIN Manager -----------------------------------------------------------
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['brand_title', 'slug']
    list_filter = ['brand_title']
    search_fields = ['brand_title']
    ordering = ['brand_title']


# Feature ADMIN Manager -----------------------------------------------------------
class FeatureValueInline(admin.TabularInline):
    model = FeatureValue
    extra = 3

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ['feature']
    filter_horizontal = ['product_groups']
    inlines = [FeatureValueInline]

@admin.register(FeatureValue)
class FeatureValueAdmin(admin.ModelAdmin):
    list_display = ['value_title']


# PRODUCT ADMIN Manager -----------------------------------------------------------
class GalleryInline(admin.TabularInline):
    model = Gallery
    extra = 1

class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        
    list_display = ['product_name', 'price', 'published_date', 'is_active', 'dis_product_groups']
    search_fields = ['product_name', 'price']
    ordering = ['is_active']
    list_editable = ['price', 'is_active']
    filter_horizontal = ['product_groups']
    inlines = [ProductFeatureInline, GalleryInline]
    fieldsets = (
        (None, {
            'fields': ('product_name', 'brand', 'product_groups', 'image_name', 'slug'),
        }),
        ('Product Info', {
            'fields': ('is_active', 'selling_type', 'price', 'published_date')
        }),
        ('Description', {
            'fields': ('summary_description', 'description')
        }),
    )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'product_groups':
            kwargs['queryset'] = ProductGroup.objects.filter(~Q(group_parent=None))
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def dis_product_groups(self, obj):
        return ', '.join([group.group_title for group in obj.product_groups.all()])