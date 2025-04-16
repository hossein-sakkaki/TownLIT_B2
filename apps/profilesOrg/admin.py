from django.contrib import admin
from django_admin_listfilter_dropdown.filters import DropdownFilter
from .models import (
                EducationProgram, OrganizationManager
            )
from .models import (
                Organization, VotingHistory,
                Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter, CounselingService,  
                WorshipStyle, ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,  
                ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization, Service,
            )
# from .forms import OrganizationManagerForm
from apps.profiles.models import Member

# POSTS MODELS Admin Inline 


# EDUCATION PROGRAM Admin --------------------------------------------------------------------------------
@admin.register(EducationProgram)
class EducationProgramAdmin(admin.ModelAdmin):
    list_display = ['program_name']
    search_fields = ['program_name']
    
    
# ORGANIZATION MANAGER Admin -------------------------------------------------------------------------------
@admin.register(OrganizationManager)
class OrganizationManagerAdmin(admin.ModelAdmin):
    # form = OrganizationManagerForm
    list_display = ['organization', 'member', 'is_approved', 'access_level', 'register_date']
    list_filter = ['organization', 'is_approved', 'access_level']
    search_fields = ['organization__org_name', 'member__name__username']
    autocomplete_fields = ['organization', 'member']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset


# ORGANIZATION MANAGER Inline ------------------------------------------------------------------------------
class OrganizationManagerInline(admin.TabularInline):
    model = OrganizationManager
    extra = 1
    autocomplete_fields = ['member']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "member":
            if request._obj_ is not None:
                kwargs["queryset"] = Member.objects.filter(organization_memberships=request._obj_)
            else:
                kwargs["queryset"] = Member.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    
# MEMBERSHIP Inline ----------------------------------------------------------------------------------------
class MemberInline(admin.TabularInline):
    model = Member.organization_memberships.through
    extra = 1
    autocomplete_fields = ['member']
    verbose_name = "Member"
    verbose_name_plural = "Members"
    

# ORGANIZATION VOTING HISTORY Admin ------------------------------------------------------------------------   
@admin.register(VotingHistory)
class VotingHistoryAdmin(admin.ModelAdmin):
    list_display = ['organization', 'voting_type', 'created_at', 'completed_at', 'result', 'total_votes', 'votes_required']
    search_fields = ['organization__org_name', 'voting_type', 'result']
    ordering = ['-created_at', 'organization']
    list_filter = ['voting_type', 'result', 'created_at', 'completed_at']

    fieldsets = (
        ('Voting Info', {'fields': ('organization', 'voting_type', 'created_at', 'completed_at', 'result')}),
        ('Voting Details', {'fields': ('total_votes', 'votes_required', 'voted_users', 'non_voted_users')}),
        ('Description', {'fields': ('description',)}),
    )
    filter_horizontal = ['voted_users', 'non_voted_users']

    def get_form(self, request, obj=None, **kwargs):
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)


# ORGANIZATION Admin ----------------------------------------------------------------------------------------
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['org_name', 'org_phone_number', 'license_expiry_date', 'is_branch', 'is_verified', 'register_date', 'verified_date', 'deletion_requested_at', 'is_suspended','reports_count']
    list_editable = ['is_branch', 'is_verified']
    search_fields = ['org_name', 'organization_services__name', 'belief', 'denominations_type']
    ordering = ['is_verified', 'is_branch', 'license_expiry_date', 'primary_language', 'secondary_language',]
    list_filter = (
        ('organization_services__name', DropdownFilter),
        ('denominations_type', DropdownFilter),
        'is_verified', 'is_branch', 'license_expiry_date',
    )
    fieldsets = (
        ('Organization Info', {'fields': ('org_name', 'org_owners', 'organization_services', 'denominations_type', 'slug')}),
        ('Branch Info', {'fields': ('is_branch', 'branch_parent')}),
        ('Team Info', {'fields': ('counselors', 'evangelists', 'leaders')}),
        ('Documents', {'fields': ('license_document', 'license_expiry_date', 'logo')}),
        ('Contact Info', {'fields': ('org_phone_number', 'org_address')}),
        ('Description', {'fields': ('history', 'belief', 'statement_of_purpose', 'primary_language', 'secondary_language', 'description', 'volunteer_opportunities')}),
        ('Permissions', {'fields': ('register_date', 'is_verified', 'verified_date', 'deletion_requested_at')}),
        ('Voting System', {'fields': ('voting_history',)}),
        ('Senctuary info', {'fields': ('last_notified', 'is_suspended','reports_count')}),
        ('Other Settings', {'fields': ('timezone_preference', 'opt_in_newsletters_emails')}),
    )
    filter_horizontal = ['org_owners', 'organization_services', 'counselors', 'evangelists', 'leaders', 'voting_history']  # اضافه کردن voting_history
    # inlines = [OrganizationManagerInline, MemberInline]

    def get_form(self, request, obj=None, **kwargs):
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)



# CHURCH Admin --------------------------------------------------------------------------------------------------
@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['pastors', 'assistant_pastors', 'teachers', 'deacons', 'worship_leaders', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name')}),
        ('Team', {'fields': ('senior_pastors', 'pastors', 'assistant_pastors', 'teachers', 'deacons', 'worship_leaders')}),
        ('Partners', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# MISSION ORGANIZATION Admin --------------------------------------------------------------------------------------
@admin.register(MissionOrganization)
class MissionOrganizationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name', 'mission_focus_areas')}),
        ('Missions', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN COUNSELING CENTER Admin --------------------------------------------------------------------------------
# Type of Servise Counseling
@admin.register(CounselingService)
class CounselingServiceAdmin(admin.ModelAdmin):
    list_display = ['service_name', 'duration', 'fee_type', 'availability', 'is_active']
    list_filter = ['fee_type', 'availability', 'is_active']
    search_fields = ['service_name', 'description']
    filter_horizontal = ['counselors']
    ordering = ['service_name']
    fieldsets = (
        ('Service Info', {'fields': ('service_name', 'description', 'duration', 'fee_type', 'availability')}),
        ('Counselors', {'fields': ('counselors',)}),
        ('Status', {'fields': ('is_active',)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('counselors')

# Christian Counseling
@admin.register(ChristianCounselingCenter)
class ChristianCounselingCenterAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['counseling_services', 'counselors', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name')}),
        ('Services', {'fields': ('counseling_services', 'counseling_methods', 'confidentiality_policy')}),
        ('Team', {'fields': ('counselors',)}),
        ('Partners', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN PUBLISHING HOUSE Admin ----------------------------------------------------------------------------------
@admin.register(ChristianPublishingHouse)
class ChristianPublishingHouseAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['authors', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name')}),
        ('Authors', {'fields': ('authors',)}),
        ('Partners', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN WORSHIP MINISTRY Admin ------------------------------------------------------------------------------------
# Worship Style
@admin.register(WorshipStyle)
class WorshipStyleAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    ordering = ['name']
    
    fieldsets = (
        ('Worship Style Info', {'fields': ('name',)}),
    )

# Worship
@admin.register(ChristianWorshipMinistry)
class ChristianWorshipMinistryAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['worship_leaders', 'worship_team', 'worship_styles', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name')}),
        ('Worship Team', {'fields': ('worship_leaders', 'worship_team')}),
        ('Worship Schedule', {'fields': ('worship_styles',)}),
        ('Partners', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN CONFERENCE CENTER Admin ------------------------------------------------------------------------------------
@admin.register(ChristianConferenceCenter)
class ChristianConferenceCenterAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name')}),
        ('Partners', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN EDUCATIONAL INSTITUTION Admin ------------------------------------------------------------------------------
@admin.register(ChristianEducationalInstitution)
class ChristianEducationalInstitutionAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'institution_type']
    filter_horizontal = ['campus_locations', 'programs_offered', 'partner_organizations', 'in_town_faculty']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name', 'institution_type')}),
        ('Locations', {'fields': ('campus_locations',)}),
        ('Faculty', {'fields': ('in_town_faculty', 'out_town_faculty')}),
        ('Programs', {'fields': ('programs_offered', 'degree_types')}),
        ('Accreditation', {'fields': ('accreditation',)}),
        ('Requirements', {'fields': ('admission_requirements',)}),
        ('Partners', {'fields': ('partner_organizations',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN CHILDREN ORGANIZATION Admin ---------------------------------------------------------------------------------
@admin.register(ChristianChildrenOrganization)
class ChristianChildrenOrganizationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['child_care_centers', 'teachers', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name', 'service_delivery_method')}),
        ('Care Centers', {'fields': ('child_care_centers',)}),
        ('Team', {'fields': ('teachers',)}),
        ('Volunteer Opportunities', {'fields': ('volunteer_opportunities',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted', 'emergency_support')}),
    )


# CHRISTIAN YOUTH ORGANIZATION Admin ------------------------------------------------------------------------------------
@admin.register(ChristianYouthOrganization)
class ChristianYouthOrganizationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['youth_centers', 'pastors', 'assistant_pastors', 'teachers', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name', 'service_delivery_method')}),
        ('Centers', {'fields': ('youth_centers',)}),
        ('Team', {'fields': ('pastors', 'assistant_pastors', 'teachers')}),
        ('Volunteer Opportunities', {'fields': ('volunteer_opportunities',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )


# CHRISTIAN WOMEN ORGANIZATION Admin ------------------------------------------------------------------------------------
@admin.register(ChristianWomensOrganization)
class ChristianWomensOrganizationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['women_centers', 'pastors', 'assistant_pastors', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name', 'service_delivery_method')}),
        ('Centers', {'fields': ('women_centers',)}),
        ('Team', {'fields': ('pastors', 'assistant_pastors')}),
        ('Volunteer Opportunities', {'fields': ('volunteer_opportunities',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted', 'emergency_support')}),
    )


# CHRISTIAN MEN ORGANIZATION Admin --------------------------------------------------------------------------------------
@admin.register(ChristianMensOrganization)
class ChristianMensOrganizationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'custom_service_name', 'is_active']
    search_fields = ['organization__org_name', 'custom_service_name']
    list_filter = ['is_active', 'is_hidden', 'is_restricted']
    filter_horizontal = ['men_centers', 'pastors', 'assistant_pastors', 'partner_organizations']
    fieldsets = (
        ('Basic Info', {'fields': ('organization', 'custom_service_name', 'service_delivery_method')}),
        ('Centers', {'fields': ('men_centers',)}),
        ('Team', {'fields': ('pastors', 'assistant_pastors')}),
        ('Volunteer Opportunities', {'fields': ('volunteer_opportunities',)}),
        ('Permissions', {'fields': ('is_active', 'is_hidden', 'is_restricted')}),
    )

# SERVICE Admin -----------------------------------------------------------------------------------------------------
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['get_organizations', 'service_type', 'specific_service_display']
    search_fields = ['organizations__org_name', 'service_type']
    list_filter = ['service_type']
    readonly_fields = ['object_id', 'specific_service']
    
    fieldsets = (
        ('Service Info', {'fields': ('organizations', 'service_type', 'content_type', 'object_id', 'specific_service')}),
    )

    def specific_service_display(self, obj):
        return str(obj.specific_service)

    def get_organizations(self, obj):
        return ", ".join([org.org_name for org in obj.organizations.all()])
    get_organizations.short_description = 'Organizations'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('organizations', 'specific_service')


