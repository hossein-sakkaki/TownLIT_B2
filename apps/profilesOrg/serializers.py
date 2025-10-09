from rest_framework import serializers
from django.utils import timezone 
from django.contrib.contenttypes.models import ContentType

from .models import (
                EducationProgram,
                Organization, OrganizationManager, VotingHistory,
                Church, MissionOrganization, ChristianPublishingHouse,
                ChristianCounselingCenter, CounselingService, WorshipStyle, ChristianWorshipMinistry,
                ChristianConferenceCenter, ChristianEducationalInstitution,
                ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization,
                Service, OrganizationService
            )
from .serializers_min import SimpleOrganizationSerializer


from apps.profiles.serializers_min import SimpleMemberSerializer
from apps.accounts.serializers import AddressSerializer, SocialMediaLinkSerializer
from apps.store.serializers import StoreSerializer

from django.contrib.auth import get_user_model

CustomUser = get_user_model()

    
# EDUCATION PROGRAM Serializer ---------------------------------------------------------------------
class EducationProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = EducationProgram
        fields = ['id', 'program_name']
        read_only_fields = ['id']


# ORGANIZATION ADMINS Serializer --------------------------------------------------------------------
class OrganizationManagerSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    member = SimpleMemberSerializer(read_only=True)

    class Meta:
        model = OrganizationManager
        fields = '__all__'
        read_only_fields = ['id', 'register_date']

    def validate_access_level(self, value):
        valid_access_levels = [OrganizationManager.FULL_ACCESS, OrganizationManager.LIMITED_ACCESS]
        if value not in valid_access_levels:
            raise serializers.ValidationError("Invalid access level.")
        return value


# ORGANIZATION VOTING HISTORY Serializer -------------------------------------------------------------   
class VotingHistorySerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    voted_users = SimpleMemberSerializer(many=True, read_only=True)
    non_voted_users = SimpleMemberSerializer(many=True, read_only=True)

    class Meta:
        model = VotingHistory
        fields = [
            'id', 'organization', 'voting_type', 'created_at', 'completed_at', 'result', 
            'total_votes', 'votes_required',  'voted_users',  'non_voted_users', 'description'
        ]
        read_only_fields = ['id', 'created_at', 'total_votes']



# ORGANIZATION SERVICE CATEGORY Serializers ---------------------------------------------------
class OrganizationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationService
        fields = '__all__'
        read_only_fields = ['id','is_active']


# ORGANIZATION Serializer -------------------------------------------------------------------------
class OrganizationSerializer(serializers.ModelSerializer):
    org_address = AddressSerializer(read_only=True)
    admins = SimpleMemberSerializer(many=True, read_only=True)
    counselors = SimpleMemberSerializer(many=True, read_only=True)
    evangelists = SimpleMemberSerializer(many=True, read_only=True)
    leaders = SimpleMemberSerializer(many=True, read_only=True)
    voting_history = VotingHistorySerializer(many=True, read_only=True)
    new_owner_request = SimpleMemberSerializer(read_only=True)
    owner_removal_request = SimpleMemberSerializer(read_only=True)
    owner_withdrawal_request = SimpleMemberSerializer(read_only=True)
    proposed_admin = SimpleMemberSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'slug', 'org_owners', 'org_name', 'org_phone_number', 'org_address',
            'denominations_type', 'organization_services', 'is_branch', 'branch_parent', 'history',
            'primary_language', 'secondary_language',
            'belief', 'statement_of_purpose', 'description', 'volunteer_opportunities', 'admins', 
            'voting_history', 'last_notified', 'is_suspended','reports_count',
            'new_owner_request', 'owner_removal_request', 'owner_withdrawal_request', 'proposed_admin', 
            'license_document', 'license_expiry_date', 'logo', 'counselors', 'evangelists', 'leaders',
            'opt_in_newsletters_emails', 'timezone_preference', 'register_date', 'is_verified',
            'verified_date', 'deletion_requested_at', 'is_hidden', 'is_active'
        ]
        read_only_fields = [
            'id', 'slug', 'register_date', 'verified_date', 'deletion_requested_at', 'is_active', 'is_suspended','reports_count', 'last_notified'
        ]

    def validate_org_phone_number(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits and numeric.")
        return value

    def validate_license_expiry_date(self, value):
        if value and value < timezone.now().date():
            raise serializers.ValidationError("License expiry date cannot be in the past.")
        return value
    
    def validate(self, data):
        if data.get('is_branch') and not data.get('branch_parent'):
            raise serializers.ValidationError("Branch organizations must have a parent organization.")
        return data


# CHURCH(ORG) Serializer ---------------------------------------------------------------------------------------------
class ChurchSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    
    class Meta:
        model = Church
        fields = [
            'id', 'organization', 'custom_service_name', 'senior_pastors', 
            'pastors', 'assistant_pastors', 'teachers', 'deacons', 'worship_leaders', 'partner_organizations',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active church must have an associated organization.")
        return data


# MISSION ORGANIZATION(ORG) Serializer ---------------------------------------------------------------------------------------
class MissionOrganizationSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)

    class Meta:
        model = MissionOrganization
        fields = [
            'id', 'organization', 'custom_service_name', 'mission_focus_areas',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active mission organization must have an associated organization.")
        return data


# CHRISTIAN PUBLISHING HOUSE(ORG) Serializer -----------------------------------------------------------------------------------
class ChristianPublishingHouseSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)

    class Meta:
        model = ChristianPublishingHouse
        fields = [
            'id', 'organization', 'custom_service_name',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active Christian Publishing House must have an associated organization.")
        return data


# CHRISTIAN COUNSELING CENTER(ORG) Serializer -----------------------------------------------------------------------------
# Counseling Service
class CounselingServiceSerializer(serializers.ModelSerializer):
    counselors = SimpleMemberSerializer(many=True, read_only=True)

    class Meta:
        model = CounselingService
        fields = [
            'id', 'service_name', 'description', 'duration', 'fee_type', 'availability', 'counselors',
            'is_active'
        ]
        read_only_fields = ['id', 'is_active']

    def validate_service_name(self, value):
        if len(value) > 50:
            raise serializers.ValidationError("Service name cannot exceed 50 characters.")
        return value

    def validate_description(self, value):
        if value and len(value) > 500:
            raise serializers.ValidationError("Description cannot exceed 500 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('service_name'):
            raise serializers.ValidationError("Active service must have a valid name.")
        return data

# Counseling Center
class ChristianCounselingCenterSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    counseling_services = CounselingServiceSerializer(many=True)

    class Meta:
        model = ChristianCounselingCenter
        fields = [
            'id', 'organization', 'custom_service_name', 'counseling_services', 'confidentiality_policy',
            'counseling_methods',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'slug', 'is_active']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active counseling center must have an associated organization.")
        return data


# CHRISTIAN WORSHIP MINISTRY(ORG) Serializer ------------------------------------------------------------------------------
# Worship Style
class WorshipStyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorshipStyle
        fields = ['id', 'name']

# Worship Ministry
class ChristianWorshipMinistrySerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    worship_styles = WorshipStyleSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChristianWorshipMinistry
        fields = [
            'id', 'organization', 'custom_service_name', 'worship_styles', 
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active worship ministry must have an associated organization.")
        return data


# CHRISTIAN CONFERENCE CENTER(ORG) Serializer -----------------------------------------------------------------------------
class ChristianConferenceCenterSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
 
    class Meta:
        model = ChristianConferenceCenter
        fields = [
            'id', 'organization', 'custom_service_name',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active conference center must have an associated organization.")
        return data


# CHRISTIAN EDUCATIONAL IINSTITUTION(ORG) Serializer ----------------------------------------------------------------------
class ChristianEducationalInstitutionSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    campus_locations = AddressSerializer(many=True, read_only=True)
    programs_offered = EducationProgramSerializer(many=True, read_only=True)

    class Meta:
        model = ChristianEducationalInstitution
        fields = [
            'id', 'organization', 'custom_service_name', 'institution_type', 'campus_locations', 'delivery_method',
            'out_town_faculty', 'accreditation', 'admission_requirements', 'programs_offered',
            'degree_types', 'scholarships_available', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate_accreditation(self, value):
        if len(value) > 255:
            raise serializers.ValidationError("Accreditation information cannot exceed 255 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active educational institution must have an associated organization.")
        return data


# CHRISTIAN CHILDREN ORGANIZATION(ORG) Serializer -------------------------------------------------------------------------
class ChristianChildrenOrganizationSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    child_care_centers = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = ChristianChildrenOrganization
        fields = [
            'id', 'organization', 'custom_service_name', 'service_delivery_method', 'child_care_centers',
            'volunteer_opportunities', 'emergency_support', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active children organization must have an associated organization.")
        return data


# CHRISTIAN YOUTH ORGANIZATION(ORG) Serializer ----------------------------------------------------------------------------
class ChristianYouthOrganizationSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    youth_centers = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = ChristianYouthOrganization
        fields = [
            'id', 'organization', 'custom_service_name', 'service_delivery_method', 'mentorship_programs',
            'youth_centers', 'volunteer_opportunities', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active youth organization must have an associated organization.")
        return data


# CHRISTIAN WOMENS ORGANIZATION(ORG) Serializer ---------------------------------------------------------------------------
class ChristianWomensOrganizationSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    women_centers = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = ChristianWomensOrganization
        fields = [
            'id', 'organization', 'custom_service_name', 'service_delivery_method', 'mentorship_programs',
            'women_centers', 'volunteer_opportunities',
            'emergency_support', 'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active women's organization must have an associated organization.")
        return data


# CHRISTIAN MENS ORGANIZATION(ORG) Serializer -----------------------------------------------------------------------------
class ChristianMensOrganizationSerializer(serializers.ModelSerializer):
    organization = SimpleOrganizationSerializer(read_only=True)
    men_centers = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = ChristianMensOrganization
        fields = [
            'id', 'organization', 'custom_service_name', 'service_delivery_method', 'mentorship_programs',
            'men_centers', 'volunteer_opportunities',
            'is_restricted', 'is_hidden', 'is_active', 'slug'
        ]
        read_only_fields = ['id', 'is_active', 'slug']

    def validate_custom_service_name(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Custom service name cannot exceed 100 characters.")
        return value

    def validate(self, data):
        if data.get('is_active') and not data.get('organization'):
            raise serializers.ValidationError("Active men's organization must have an associated organization.")
        return data


# Service Organization Serializer -----------------------------------------------------------------------------------------
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import Service

# Service Organization Serializer -----------------------------------------------------------------------------------------
class ServiceSerializer(serializers.ModelSerializer):
    specific_service = serializers.SerializerMethodField()
    organizations = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), many=True)

    class Meta:
        model = Service
        fields = ['id', 'organization', 'service_type', 'specific_service']
        read_only_fields = ['id']

    def get_specific_service(self, instance):
        # For Appropriate Content Type Choice
        content_type = ContentType.objects.get_for_model(instance.specific_service)
        
        if content_type.model == 'church':
            return ChurchSerializer(instance.specific_service).data
        elif content_type.model == 'missionorganization':
            return MissionOrganizationSerializer(instance.specific_service).data
        elif content_type.model == 'christianpublishinghouse':
            return ChristianPublishingHouseSerializer(instance.specific_service).data
        elif content_type.model == 'christiancounselingcenter':
            return ChristianCounselingCenterSerializer(instance.specific_service).data
        elif content_type.model == 'christianworshipministry':
            return ChristianWorshipMinistrySerializer(instance.specific_service).data
        elif content_type.model == 'christianconferencecenter':
            return ChristianConferenceCenterSerializer(instance.specific_service).data
        elif content_type.model == 'christianeducationalinstitution':
            return ChristianEducationalInstitutionSerializer(instance.specific_service).data
        elif content_type.model == 'christianchildrenorganization':
            return ChristianChildrenOrganizationSerializer(instance.specific_service).data
        elif content_type.model == 'christianyouthorganization':
            return ChristianYouthOrganizationSerializer(instance.specific_service).data
        elif content_type.model == 'christianwomensorganization':
            return ChristianWomensOrganizationSerializer(instance.specific_service).data
        elif content_type.model == 'christianmensorganization':
            return ChristianMensOrganizationSerializer(instance.specific_service).data
        elif content_type.model == 'store':
            return StoreSerializer(instance.specific_service).data
        else:
            return None

    def to_representation(self, instance):
         # Dynamic representation for specific_service based on content_type
        representation = super().to_representation(instance)
        specific_service = self.get_specific_service(instance)
        if specific_service:
            representation['specific_service'] = specific_service
        return representation



