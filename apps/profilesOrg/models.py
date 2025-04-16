from django.db import models
from django.urls import reverse
from django.utils import timezone 
from uuid import uuid4
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.accounts.models import (
                            Address, SocialMediaLink,
                        )
from apps.profiles.models import Member
from apps.accounts.models import OrganizationService
from apps.posts.models import Testimony
from apps.config.profiles_constants import EDUCATION_DEGREE_CHOICES
from apps.config.constants import (
                            DELIVERY_METHOD_CHOICES, TIMEZONE_CHOICES, 
                            CHURCH_DENOMINATIONS_CHOICES,
                        )
from apps.config.organization_constants import (
                            LANGUAGE_CHOICES, ENGLISH, PROGRAM_NAME_CHOICES, ACCESS_LEVEL_CHOICES,
                            ORGANIZATION_TYPE_CHOICES, COUNSELING_SERVICE_CHOICES, PRICE_TYPE_CHOICES,
                            WORSHIP_STYLE_CHOICES, INSTITUTION_TYPE_CHOICES, VOTING_TYPE_CHOICES, VOTING_RESULT_CHOICES
                        )
from common.validators import (
                            validate_pdf_file,
                            validate_no_executable_file,
                            validate_phone_number,
                            validate_image_or_video_file
                        )
from utils import FileUpload, SlugMixin
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# EDUCATION PROGRAM Model ---------------------------------------------------------------------------------
class EducationProgram(models.Model):
    program_name = models.CharField(max_length=255, choices=PROGRAM_NAME_CHOICES, verbose_name='Program Name')
    def __str__(self):
        return self.program_name
    def get_absolute_url(self):
        return reverse("education_program_detail", kwargs={"pk": self.pk})
    
    
# ORGANIZATION ADMINS Manager -----------------------------------------------------------------------------
class OrganizationManager(models.Model):
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, db_index=True, related_name='admin_relationships', verbose_name='Organization')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, db_index=True, related_name='organization_adminships', verbose_name='Member')
    is_approved = models.BooleanField(default=False, verbose_name='Is Approved')
    access_level = models.CharField(max_length=15, choices=ACCESS_LEVEL_CHOICES, verbose_name='Access Level')    
    is_being_replaced = models.BooleanField(default=False, verbose_name="Is Being Replaced")    
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')

    class Meta:
        unique_together = ('organization', 'member')
        verbose_name = 'Organization Manager'
        verbose_name_plural = 'Organization Managers'

    def get_absolute_url(self):
        return reverse("organization_manager_detail", kwargs={"pk": self.pk})
  
    
 # ORGANIZATION VOTING HISTORY Model ----------------------------------------------------------------------   
class VotingHistory(models.Model):
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='voting_histories', verbose_name="Organization")
    voting_type = models.CharField(max_length=50, choices=VOTING_TYPE_CHOICES, verbose_name="Voting Type")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Completed At")
    result = models.CharField(max_length=50, choices=VOTING_RESULT_CHOICES, null=True, blank=True, verbose_name="Result")

    total_votes = models.IntegerField(default=0, verbose_name="Total Votes")
    votes_required = models.IntegerField(verbose_name="Votes Required")
    voted_users = models.ManyToManyField(Member, related_name='voted_in_history', verbose_name="Voted Users")
    non_voted_users = models.ManyToManyField(Member, related_name='non_voted_in_history', verbose_name="Non-voted Users")

    description = models.TextField(null=True, blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Voting History"
        verbose_name_plural = "Voting Histories"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_voting_type_display()} - {self.organization.org_name}"


# ORGANIZATION Manager ------------------------------------------------------------------------------------
class Organization(SlugMixin):
    LICENSE = FileUpload('profiles_org', 'documents', 'organizations')
    LOGO = FileUpload('profiles_org', 'logos', 'organizations')

    org_owners = models.ManyToManyField(Member, related_name='organization_owners', verbose_name='Organization Owner/Owners')
    org_name = models.CharField(max_length=100, db_index=True, verbose_name='Organization Name')

    org_phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True, validators=[validate_phone_number], verbose_name='Phone Number')
    org_address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, related_name='organization_address', verbose_name='Organization Address')

    denominations_type = models.CharField(max_length=40, choices=CHURCH_DENOMINATIONS_CHOICES, verbose_name='Denominations Type')
    organization_services = models.ManyToManyField(OrganizationService, verbose_name='Organization Services')
    services = models.ManyToManyField('Service', blank=True, related_name='organization_services', verbose_name='Services')

    primary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default=ENGLISH, verbose_name='Primary Language')
    secondary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, null=True, blank=True, verbose_name='Secondary Language')

    is_branch = models.BooleanField(default=False, verbose_name='Is Branch')
    branch_parent = models.ForeignKey('Organization' ,on_delete=models.PROTECT, null=True, blank=True, related_name='organization_branch', verbose_name='Branch of Organization') 
    history = models.TextField(null=True, blank=True, verbose_name='History')
    belief = models.TextField(null=True, blank=True, verbose_name='Letter of Beleif')
    statement_of_purpose = models.TextField(null=True, blank=True, verbose_name='Statement of Purpose')
    description = models.TextField(null=True, blank=True, verbose_name='Description of Organization')
    volunteer_opportunities = models.TextField(null=True, blank=True, verbose_name='Volunteer Opportunities')

    admins = models.ManyToManyField(Member, through='OrganizationManager', related_name='admin_organizations', verbose_name='Admins')
    counselors = models.ManyToManyField(Member, blank=True, related_name='organization_counselors', verbose_name='Counselors')
    evangelists = models.ManyToManyField(Member, blank=True, related_name='organization_evangelists', verbose_name='Evangelists')
    leaders = models.ManyToManyField(Member, blank=True, related_name='organization_leaders', verbose_name='Leaders')
    
    license_document = models.FileField(upload_to=LICENSE.dir_upload, blank=True, null=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='License Document')
    license_expiry_date = models.DateField(blank=True, null=True, verbose_name='License Expiry Date')
    logo = models.ImageField(upload_to=LOGO.dir_upload, default='media/sample/logo.png', validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Logo')

    # Voting System For Organizations
    voting_history = models.ManyToManyField(VotingHistory, related_name='voted_organizations', blank=True, verbose_name='Voting History')
    new_owner_request = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='pending_organization_ownership', verbose_name='New Owner Request')
    owner_removal_request = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='pending_organization_removal', verbose_name='Owner Removal Request')
    owner_withdrawal_request = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name='pending_owner_withdrawal', verbose_name='Owner Withdrawal Request')
    proposed_admin = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='proposed_admin_for_orgs', verbose_name='Proposed New Admin')

    opt_in_newsletters_emails = models.BooleanField(default=True, verbose_name='Opt-in for Newsletters Emails')
    timezone_preference = models.CharField(max_length=100, choices=TIMEZONE_CHOICES, verbose_name='Timezone Preference')
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')
 
    last_notified = models.DateTimeField(null=True, blank=True)   
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")

    is_verified = models.BooleanField(default=False, verbose_name='Is Verified')
    verified_date = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True, verbose_name='Verified Date')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    deletion_requested_at = models.DateTimeField(null=True, blank=True, verbose_name='Deletion Requested At')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'organization_detail'
    
    def get_slug_source(self):
        return self.org_name
    
    class Meta:
        verbose_name = "1. Organization"
        verbose_name_plural = "1. Organization" 
    
    def __str__(self):
        return self.org_name
    
    
# CHURCH(ORG) Manager --------------------------------------------------------------------------------------------------
class Church(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='church_details', verbose_name='Church Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    senior_pastors = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, blank=True, related_name='church_senior_pastors', verbose_name='Church Senior Pastors')
    pastors = models.ManyToManyField(Member, blank=True, related_name='church_pastors', verbose_name='Church Pastors')
    assistant_pastors = models.ManyToManyField(Member, blank=True, related_name='church_assistant_pastors', verbose_name='Church Assistant Pastors')
    teachers = models.ManyToManyField(Member, blank=True, related_name='church_teachers', verbose_name='Church Teachers')
    deacons = models.ManyToManyField(Member, blank=True, related_name='church_deacons', verbose_name='Church Deacons')
    worship_leaders = models.ManyToManyField(Member, blank=True, related_name='church_worship_leaders', verbose_name='Church Worship Leaders')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_church', verbose_name='Partner Organizations')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'church_detail'

    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"

    class Meta:
        verbose_name = "Church"
        verbose_name_plural = "Churchs"

    def __str__(self):
        return f"{self.custom_service_name or 'Church'}: {self.organization.org_name}"


# MISSION ORGANIZATION(ORG) Manager ---------------------------------------------------------------------------------------
class MissionOrganization(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='mission_organization_details', verbose_name='Mission Organization Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    mission_focus_areas = models.TextField(null=True, blank=True, verbose_name='Mission Focus Areas')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_mission_org', verbose_name='Partner Organizations')

    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'mission_organization_detail'
        
    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"

    class Meta:
        verbose_name = "Mission Organization"
        verbose_name_plural = "Mission Organizations"

    def __str__(self):
        return f"{self.custom_service_name or 'Mission Organization'}: {self.organization.org_name}"


# CHRISTIAN PUBLISHING HOUSE(ORG) Manager -----------------------------------------------------------------------------------
class ChristianPublishingHouse(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_publishing_house_details', verbose_name='Christian Publishing House Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    authors = models.ManyToManyField(CustomUser, blank=True, related_name='publishing_house_authors', verbose_name='Publishing House Authors')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_publishing_house', verbose_name='Partner Organizations')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_publishing_house_detail'
    
    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"
    
    class Meta:
        verbose_name = "Christian Publishing House"
        verbose_name_plural = "Christian Publishing Houses"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Publishing House'}: {self.organization.org_name}"


# CHRISTIAN COUNSELING CENTER(ORG) Manager -----------------------------------------------------------------------------------
class ChristianCounselingCenter(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_counseling_center_details', verbose_name='Christian Counseling Center Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    counseling_services = models.ManyToManyField('CounselingService', blank=True, related_name='counseling_services', verbose_name='Counseling Services')
    confidentiality_policy = models.TextField(null=True, blank=True, verbose_name='Confidentiality Policy')
    counselors = models.ManyToManyField(Member, blank=True, related_name='counseling_center_counselors', verbose_name='Counselors')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_counseling_center', verbose_name='Partner Organizations')
    counseling_methods = models.CharField(max_length=100, choices=DELIVERY_METHOD_CHOICES, verbose_name='Counseling Methods')
    testimonials = models.ManyToManyField(Testimony, blank=True, related_name='counseling_testimonials', verbose_name='Counseling Testimonials')

    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_counseling_center_detail'

    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"

    class Meta:
        verbose_name = "Christian Counseling Center"
        verbose_name_plural = "Christian Counseling Centers"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Counseling Center'}: {self.organization.org_name}"

    
# Counseling Service
class CounselingService(models.Model):
    service_name = models.CharField(max_length=50, choices=COUNSELING_SERVICE_CHOICES, verbose_name='Service Name')
    description = models.CharField(max_length= 500, null=True, blank=True, verbose_name='Description')
    duration = models.DurationField(null=True, blank=True, verbose_name='Session Duration')
    fee_type = models.CharField(max_length=10, choices=PRICE_TYPE_CHOICES, verbose_name='Fee Type')
    availability = models.CharField(max_length=10, choices=DELIVERY_METHOD_CHOICES, verbose_name='Availability')
    counselors = models.ManyToManyField(Member, blank=True, related_name='counseling_services')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    def __str__(self):
        return self.service_name

    class Meta:
        verbose_name = "Counseling Service"
        verbose_name_plural = "Counseling Services"
        
    def get_absolute_url(self):
        return reverse("counseling_service_detail", kwargs={"pk": self.pk})
        

# CHRISTIAN WORSHIP MINISTRY(ORG) Manager --------------------------------------------------------------------------------------
class WorshipStyle(models.Model):
    name = models.CharField(max_length=100, choices=WORSHIP_STYLE_CHOICES, unique=True, verbose_name='Worship Style Name')
    def __str__(self):
        return self.name
    def get_absolute_url(self):
        return reverse("worship_style_detail", kwargs={"pk": self.pk})

# Christian Worship Ministry
class ChristianWorshipMinistry(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_worship_ministry_details', verbose_name='Christian Worship Ministry Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    worship_leaders = models.ManyToManyField(Member, blank=True, related_name='organization_worship_leaders', verbose_name='Worship Leaders')
    worship_team = models.ManyToManyField(Member, blank=True, related_name='worship_team_members', verbose_name='Worship Team')
    worship_styles = models.ManyToManyField(WorshipStyle, blank=True, related_name='worship_ministries', verbose_name='Worship Styles')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_worship_ministry', verbose_name='Partner Organizations')

    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_worship_ministry_detail'
    
    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"

    class Meta:
        verbose_name = "Christian Worship Ministry"
        verbose_name_plural = "Christian Worship Ministries"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Worship Ministry'}: {self.organization.org_name}"


# CHRISTIAN CONFERENCE CENTER(ORG) Manager ---------------------------------------------------------------------------
class ChristianConferenceCenter(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_conference_center_details', verbose_name='Christian Conference Center Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_christian_conference_center', verbose_name='Partner Organizations')

    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_conference_center_detail'

    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"

    class Meta:
        verbose_name = "Christian Conference Center"
        verbose_name_plural = "Christian Conference Centers"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Conference Center'}: {self.organization.org_name}"
    
    
# CHRISTIAN EDUCATIONAL IINSTITUTION(ORG) Manager ---------------------------------------------------------------------------
class ChristianEducationalInstitution(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_educational_institution_details', verbose_name='Christian Educational Institution Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    institution_type = models.CharField(max_length=50, choices=INSTITUTION_TYPE_CHOICES, verbose_name='Institution Type')
    campus_locations = models.ManyToManyField(Address, blank=True, related_name='campuses', verbose_name='Campus Locations')
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_METHOD_CHOICES, verbose_name='Delivery Method')
    in_town_faculty = models.ManyToManyField(Member, blank=True, related_name='faculty_members', verbose_name='Faculty in TownLIT')
    out_town_faculty = models.CharField(max_length=200, null=True, blank=True, verbose_name='Faculty out TownLIT')
    accreditation = models.CharField(max_length=255, null=True, blank=True, verbose_name='Accreditation')
    admission_requirements = models.TextField(null=True, blank=True, verbose_name='Admission Requirements')
    programs_offered = models.ManyToManyField(EducationProgram, blank=True, related_name='offered_by_institutions', verbose_name='Programs Offered')
    degree_types = models.CharField(max_length=100, null=True, blank=True, choices=EDUCATION_DEGREE_CHOICES, verbose_name='Degree Types')
    scholarships_available = models.BooleanField(default=False, verbose_name='Scholarships Available')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_christian_educational_institution', verbose_name='Partner Organizations')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_educational_institution_detail'

    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"

    class Meta:
        verbose_name = "Christian Educational Institution"
        verbose_name_plural = "Christian Educational Institutions"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Educational Institution'}: {self.organization.org_name}"


# CHRISTIAN CHILDREN ORGANIZATION(ORG) Manager ---------------------------------------------------------------------------
class ChristianChildrenOrganization(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_children_organization_details', verbose_name='Christian Children Organization Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    service_delivery_method = models.CharField(max_length=10, blank=True, null=True, choices=DELIVERY_METHOD_CHOICES, verbose_name='Service Delivery Method')
    child_care_centers = models.ManyToManyField(Address, blank=True, related_name='care_centers_for_children', verbose_name='Child Care Centers')
    volunteer_opportunities = models.TextField(null=True, blank=True, verbose_name='Volunteer Opportunities')
    teachers = models.ManyToManyField(Member, blank=True, related_name='children_teachers', verbose_name='Children Teachers')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_children_orgs', verbose_name='Partner Organizations')
    emergency_support = models.BooleanField(default=False, verbose_name='Emergency Support Available')

    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_children_organization_detail'

    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"
        
    class Meta:
        verbose_name = "Christian Children's Organization"
        verbose_name_plural = "Christian Children's Organizations"
        
    def __str__(self):
        return f"{self.custom_service_name or 'Christian Children Organization'}: {self.organization.org_name}"


# CHRISTIAN YOUTH ORGANIZATION(ORG) Manager ---------------------------------------------------------------------------
class ChristianYouthOrganization(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_youth_organization_details', verbose_name='Christian Youth Organization Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    service_delivery_method = models.CharField(max_length=10, blank=True, null=True, choices=DELIVERY_METHOD_CHOICES, verbose_name='Service Delivery Method')
    mentorship_programs = models.TextField(null=True, blank=True, verbose_name='Mentorship Programs') # Example: "Our mentorship programs include weekly sessions with experienced mentors who help young people identify their goals and plan strategies to achieve them. These programs also offer group and individual sessions to discuss the challenges of Christian life, spiritual growth, and social issues."
    youth_centers = models.ManyToManyField(Address, blank=True, related_name='youth_centers', verbose_name='Youth Centers')
    volunteer_opportunities = models.TextField(null=True, blank=True, verbose_name='Volunteer Opportunities')

    pastors = models.ManyToManyField(Member, blank=True, related_name='youth_pastors', verbose_name='Youth Pastors')
    assistant_pastors = models.ManyToManyField(Member, blank=True, related_name='youth_assistant_pastors', verbose_name='Youth Assistant Pastors')
    teachers = models.ManyToManyField(Member, blank=True, related_name='youth_teachers', verbose_name='Youth Teachers')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_youth_orgs', verbose_name='Partner Organizations')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'christian_youth_organization_detail'

    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"
        
    class Meta:
        verbose_name = "Christian Youth Organization"
        verbose_name_plural = "Christian Youth Organizations"
        
    def __str__(self):
        return f"{self.custom_service_name or 'Christian Youth Organization'}: {self.organization.org_name}"


# CHRISTIAN WOMENS ORGANIZATION(ORG) Manager ---------------------------------------------------------------------------
class ChristianWomensOrganization(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_womens_organization_details', verbose_name='Christian Womens Organization Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    service_delivery_method = models.CharField(max_length=10, blank=True, null=True, choices=DELIVERY_METHOD_CHOICES, verbose_name='Service Delivery Method')
    mentorship_programs = models.TextField(null=True, blank=True, verbose_name='Mentorship Programs')
    women_centers = models.ManyToManyField(Address, blank=True, related_name='women_centers', verbose_name='Women Centers')
    volunteer_opportunities = models.TextField(null=True, blank=True, verbose_name='Volunteer Opportunities')

    pastors = models.ManyToManyField(Member, blank=True, related_name='women_pastors', verbose_name='Women Pastors')
    assistant_pastors = models.ManyToManyField(Member, blank=True, related_name='women_assistant_pastors', verbose_name='Women Assistant Pastors')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_women_orgs', verbose_name='Partner Organizations')
    emergency_support = models.BooleanField(default=False, verbose_name='Emergency Support Available')

    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active') 
    url_name = 'christian_womens_organization_detail' 
        
    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"
    
    class Meta:
        verbose_name = "Christian Women's Organization"
        verbose_name_plural = "Christian Women's Organizations"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Womens Organization'}: {self.organization.org_name}"


# CHRISTIAN MENS ORGANIZATION(ORG) Manager ---------------------------------------------------------------------------
class ChristianMensOrganization(SlugMixin):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='christian_mens_organization_details', verbose_name='Christian Mens Organization Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    service_delivery_method = models.CharField(max_length=10, blank=True, null=True, choices=DELIVERY_METHOD_CHOICES, verbose_name='Service Delivery Method')
    mentorship_programs = models.TextField(null=True, blank=True, verbose_name='Mentorship Programs')
    men_centers = models.ManyToManyField(Address, blank=True, related_name='men_centers', verbose_name='Men Centers')
    volunteer_opportunities = models.TextField(null=True, blank=True, verbose_name='Volunteer Opportunities')
    
    pastors = models.ManyToManyField(Member, blank=True, related_name='men_pastors', verbose_name='Men Pastors')
    assistant_pastors = models.ManyToManyField(Member, blank=True, related_name='men_assistant_pastors', verbose_name='Men Assistant Pastors')
    partner_organizations = models.ManyToManyField(Organization, blank=True, related_name='partners_with_men_orgs', verbose_name='Partner Organizations')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')   
    url_name = 'christian_mens_organization_detail' 


    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"
        
    class Meta:
        verbose_name = "Christian Men's Organization"
        verbose_name_plural = "Christian Men's Organizations"

    def __str__(self):
        return f"{self.custom_service_name or 'Christian Mens Organization'}: {self.organization.org_name}" 
 
 
# SERVICE ORGANIZATION Manager ---------------------------------------------------------------------------
class Service(models.Model):
    organizations = models.ManyToManyField(Organization, related_name='service_relations', verbose_name='Organizations')
    service_type = models.CharField(max_length=50, choices=ORGANIZATION_TYPE_CHOICES, verbose_name='Service Type')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    specific_service = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"{self.get_service_type_display()} for {self.organization.org_name}"

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def get_absolute_url(self):
        return reverse("service_detail", kwargs={"pk": self.pk})
    