from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from colorfield.fields import ColorField
from django.db.models import Q
from django import forms  
from django.utils.html import format_html

from .forms import UserCreationForm, UserChangeForm
from .models import (
                Address, CustomLabel, SocialMediaType, SocialMediaLink,
                InviteCode, UserDeviceKey
            )
from apps.profiles.models import Friendship
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# ADDRESS Admin ---------------------------------------------------------------------
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['street_number', 'route', 'locality', 'administrative_area_level_1', 'postal_code', 'country', 'address_type']
    search_fields = ['street_number', 'route', 'locality', 'administrative_area_level_1', 'postal_code', 'country']
    list_filter = ['country', 'locality', 'administrative_area_level_1']
    readonly_fields = ['additional']
    
# CustomLabel Admin ---------------------------------------------------------------------
@admin.register(CustomLabel)
class CustomLabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'description', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    list_filter = ['is_active']
    ordering = ['name']
    formfield_overrides = {
        ColorField: {'widget': forms.TextInput(attrs={'type': 'color'})},
    }

# SOCIAL MEDIA TYPE Admin --------------------------------------------------------------
@admin.register(SocialMediaType)
class SocialMediaTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon_class', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active']
    list_filter = ['is_active']

# URL LINKS Admin -----------------------------------------------------------------------
# @admin.register(SocialMediaLink)
# class SocialMediaLinkAdmin(admin.ModelAdmin):
#     list_display = ['social_media_type', 'link', 'is_active']
#     search_fields = ['link', 'description']
#     list_filter = ['social_media_type', 'is_active']
#     autocomplete_fields = ['social_media_type']


# Friendship Inline Admin -------------------------------------------------------------    
class FriendshipInline(admin.TabularInline):
    model = Friendship
    fields = ('to_user', 'status', 'created_at')
    extra = 0
    verbose_name_plural = 'Friendships'
    can_delete = True
    fk_name = 'from_user'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(Q(from_user=request.user) | Q(to_user=request.user))
    
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        if isinstance(obj, Friendship):
            return request.user == obj.from_user or request.user == obj.to_user
        return False 


# CUSTOMUSER ADMIN Manager -----------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ['email', 'name', 'family', 'username', 'gender', 'label', 'pin_security_enabled', 'two_factor_enabled', 'is_member', 'is_active', 'is_admin', 'is_suspended', 'is_deleted', 'reports_count', 'is_account_paused', 'register_date', 'profile_image_thumbnail']
    list_filter = ['is_active', 'is_admin', 'gender', 'label', 'register_date']
    list_editable = ['is_active', 'is_admin', 'is_member'] 
    search_fields = ['username', 'mobile_number', 'name']
    readonly_fields = ['register_date', 'last_login']
    fieldsets = (
        ('Account Info', {'fields': ('mobile_number', 'mobile_verification_code', 'password', 'username', 'registration_id', 'is_account_paused')}),
        ('Personal info', {'fields': ('name', 'family', 'email', 'last_email_change', 'email_change_tokens', 'gender', 'label', 'birthday', 'country', 'city', 'primary_language', 'secondary_language', 'image_name')}),
        ('Sanctuary info', {'fields': ('is_suspended', 'reports_count')}),
        ('Expiry date info', {'fields': ('user_active_code_expiry', 'mobile_verification_expiry', 'reset_token_expiration')}),
        # ('Keys & Security', {'fields': ('two_factor_enabled'),}),
        ('Deleted Info', {'fields': ('pin_security_enabled', 'deletion_requested_at', 'is_deleted', 'reactivated_at')}),
        ('Permissions', {'fields': ('show_email', 'show_phone_number', 'show_country', 'show_city', 'is_active', 'is_member', 'is_admin', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'mobile_number', 'name', 'family', 'username', 'birthday', 'gender', 'label', 'country', 'city', 'image_name', 'password'),
        }),
    )
    filter_horizontal = ('groups', 'user_permissions') 
    inlines = [FriendshipInline]
    
    def get_inline_instances(self, request, obj=None):
        if obj:
            return [inline(self.model, self.admin_site) for inline in self.inlines]
        return []

    def profile_image_thumbnail(self, obj):
        if obj.image_name:
            return format_html('<img src="{}" width="30" height="30" style="border-radius:50%;" />', obj.image_name.url)
        return ''
    
    profile_image_thumbnail.short_description = 'Profile Image'
    

# Invite Code Admin ---------------------------------------------------------------------
@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'email', 'is_used', 'used_by', 'created_at', 'used_at', 'invite_email_sent', 'invite_email_sent_at']
    search_fields = ['code', 'email']
    list_filter = ['is_used']
    

# User Device Key Admin ------------------------------------------------------------------
@admin.register(UserDeviceKey)
class UserDeviceKeyAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'device_name', 'device_id', 'ip_address',
        'location_city', 'location_region', 'location_country',
        'timezone', 'organization', 'postal_code',
        'latitude', 'longitude',
        'last_used', 'is_active',
    )
    list_filter = (
        'is_active', 'location_country', 'location_region', 'organization', 'timezone'
    )
    search_fields = (
        'user__email', 'device_id', 'device_name', 'ip_address',
        'location_city', 'location_region', 'location_country',
        'organization', 'postal_code'
    )
    readonly_fields = (
        'created_at', 'last_used', 'ip_address',
        'location_city', 'location_region', 'location_country',
        'timezone', 'organization', 'postal_code',
        'latitude', 'longitude',
    )
    ordering = ('-last_used',)
