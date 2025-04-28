from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.admin import GenericTabularInline

from apps.posts.models import Moment, Pray
from .models import (
                AcademicRecord,
                Friendship, MigrationHistory,
                GuestUser,
                Member, MemberServiceType,
                Client, ClientRequest,
                Customer,
                SpiritualGift, SpiritualGiftSurveyQuestion,
                SpiritualGiftSurveyResponse, MemberSpiritualGifts
            )
from apps.profilesOrg.models import OrganizationManager

# Friendship Admin ---------------------------------------------------------------------
@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('initiator', 'friend', 'created_at', 'deleted_at', 'status_display', 'is_active')
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
            'pending_deletion': 'grey'
        }
        return format_html("<span style='color: {};'>{}</span>", color_map.get(obj.status, 'black'), obj.status.capitalize())

    initiator.admin_order_field = 'from_user__username'
    friend.admin_order_field = 'to_user__username'
    status_display.short_description = 'Status'


# Education Models Admin -----------------------------------------------------------------
class AcademicRecordInline(admin.TabularInline):
    model = AcademicRecord
    extra = 1
    fields = ['education_document_type', 'education_degree', 'school', 'country', 'graduation_year', 'document', 'is_teology_related']
    readonly_fields = ['document']
    show_change_link = True


# AcademicRecord Admin --------------------------------------------------------------------
@admin.register(AcademicRecord)
class AcademicRecordAdmin(admin.ModelAdmin):
    list_display = ['education_document_type', 'education_degree', 'school', 'country', 'graduation_year', 'is_teology_related']
    list_filter = ['education_degree', 'country', 'graduation_year', 'is_teology_related']
    search_fields = ['school', 'country', 'graduation_year']
    readonly_fields = ['document']
    ordering = ['graduation_year']


# MIGRATION HISTORY Admin ------------------------------------------------------------
class MigrationHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'migration_type', 'migration_date')
    search_fields = ('user__username', 'migration_type')
    list_filter = ('migration_type', 'migration_date')

admin.site.register(MigrationHistory, MigrationHistoryAdmin)


# MEMBER ADMIN Manager ----------------------------------------------------------- 
# Member Service
@admin.register(MemberServiceType)
class MemberServiceTypeAdmin(admin.ModelAdmin):
    list_display = ['service', 'is_approved', 'is_active', 'register_date']
    list_filter = ['is_approved', 'is_active', 'register_date']
    search_fields = ['service__name', 'history']
    
    fieldsets = (
        ('Service Info', {'fields': ('service', 'history')}),
        ('Documents', {'fields': ('document',)}),
        ('Status', {'fields': ('is_approved', 'is_active')}),
        ('Dates', {'fields': ('register_date',)}),
    )
    autocomplete_fields = ['service']

# Organization Manager Inline
class OrganizationManagerInMemberInline(admin.TabularInline):
    model = OrganizationManager
    extra = 1

# MOMENT Admin Inline
class MomentInline(GenericTabularInline):
    model = Moment
    extra = 0
    readonly_fields = ['content', 'published_at']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(content_type=ContentType.objects.get_for_model(Member))

# PRAY Admin Inline
class PrayInline(GenericTabularInline):
    model = Pray
    extra = 0
    readonly_fields = ['title', 'content', 'published_at']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(content_type=ContentType.objects.get_for_model(Member))


# Member Admin
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'spiritual_rebirth_day', 'is_migrated', 'is_active', 'is_privacy', 'register_date', 'identity_verification_status', 'is_verified_identity', 'is_sanctuary_participant','is_hidden_by_confidants']
    list_filter = ['is_migrated', 'is_active', 'is_privacy', 'register_date']
    search_fields = ['user__username', 'biography', 'vision', 'service_types__service__name']
    autocomplete_fields = ['user', 'testimony']
    filter_horizontal = ['service_types', 'organization_memberships']
    fieldsets = (
        ('Personal Info', {'fields': ('user', 'biography', 'vision', 'spiritual_rebirth_day', 'denominations_type', 'show_gifts_in_profile','show_fellowship_in_profile')}),
        ('Services', {'fields': ('service_types', 'academic_record')}),
        ('Organizations & Memberships', {'fields': ('organization_memberships',)}),
        ('Testimonies & Moments', {'fields': ('testimony',)}),
        ('Status', {'fields': ('is_migrated', 'is_active', 'is_privacy', 'identity_verification_status', 'identity_verified_at', 'is_verified_identity', 'is_sanctuary_participant',)}),
        ('Dates', {'fields': ('register_date',)}),
    )
    # inlines = [OrganizationManagerInMemberInline]
    inlines = [MomentInline, PrayInline]
    
    def get_form(self, request, obj=None, **kwargs):
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)

    def managed_organizations_display(self, obj):
        return ', '.join([org.org_name for org in obj.managed_organizations()])
    managed_organizations_display.short_description = 'Managed Organizations'


# GUESTUSER MOMENT Admin Inline
class GuestUserMomentInline(GenericTabularInline):
    model = Moment
    extra = 0
    readonly_fields = ['content', 'published_at']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(content_type=ContentType.objects.get_for_model(GuestUser))
    
    
# GUEST USER ADMIN Manager -----------------------------------------------------------
@admin.register(GuestUser)
class GuestUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'register_date', 'is_migrated', 'is_active']
    list_filter = ['is_migrated', 'is_active', 'register_date']
    search_fields = ['user__username']
    ordering = ['register_date', 'is_migrated', 'is_active']
    fieldsets = (
        ('User Info', {'fields': ('user',)}),
        ('Status', {'fields': ('is_migrated', 'is_active')}),
        ('Dates', {'fields': ('register_date',)}),
    )
    inlines = [GuestUserMomentInline]


# CUSTOMER ADMIN Manager -----------------------------------------------------------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'customer_phone_number', 'billing_address', 'get_shipping_addresses', 'register_date', 'is_active']
    list_filter = ['is_active', 'register_date', 'deactivation_reason']
    search_fields = ['user__username', 'customer_phone_number']

    fieldsets = (
        ('Customer Info', {'fields': ('user', 'customer_phone_number', 'billing_address', 'shipping_addresses')}),
        ('Status', {'fields': ('is_active', 'deactivation_reason', 'deactivation_note')}),
        ('Dates', {'fields': ('register_date',)}),
    )

    autocomplete_fields = ['billing_address', 'shipping_addresses']

    def get_shipping_addresses(self, obj):
        return ", ".join([str(address) for address in obj.shipping_addresses.all()])
    get_shipping_addresses.short_description = 'Shipping Addresses'

    

# CLIENT ADMIN Manager -----------------------------------------------------------
# Request
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

# Client Admin
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


# Gift Admin ----------------------------------------------------------------------
@admin.register(SpiritualGift)
class SpiritualGiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)

@admin.register(SpiritualGiftSurveyQuestion)
class SpiritualGiftSurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'question_number', 'language', 'gift')
    search_fields = ('question_text', 'question_number', 'language',)
    list_filter = ('language', 'gift')
    ordering = ('gift',)

@admin.register(SpiritualGiftSurveyResponse)
class SpiritualGiftSurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('member', 'question', 'answer')
    # search_fields = ('member__username', 'question__question_text',)
    search_fields = ('member__user__username', 'question__question_text',)
    list_filter = ('question',)
    ordering = ('member',)

@admin.register(MemberSpiritualGifts)
class MemberSpiritualGiftsAdmin(admin.ModelAdmin):
    list_display = ('member', 'get_gifts', 'survey_results')
    search_fields = ('member__user__username',)
    # search_fields = ('member__username',)
    list_filter = ('member',)
    ordering = ('member',)

    def get_gifts(self, obj):
        return ", ".join([gift.name for gift in obj.gifts.all()])
    get_gifts.short_description = _('Spiritual Gifts')
