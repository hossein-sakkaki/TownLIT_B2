from django.shortcuts import render
from django.utils import timezone

from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .models import (
                Organization, OrganizationManager, Service,
                Church, MissionOrganization, ChristianPublishingHouse,
                ChristianCounselingCenter, CounselingService, ChristianWorshipMinistry,
                ChristianConferenceCenter, ChristianEducationalInstitution, 
                ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
            )
from .serializers import (
                OrganizationSerializer, ServiceSerializer, OrganizationManagerSerializer,
                ChurchSerializer, MissionOrganizationSerializer, ChristianPublishingHouseSerializer,
                ChristianCounselingCenterSerializer, CounselingServiceSerializer, ChristianWorshipMinistrySerializer,
                ChristianConferenceCenterSerializer, ChristianEducationalInstitutionSerializer,
                ChristianChildrenOrganizationSerializer,  ChristianYouthOrganizationSerializer, ChristianWomensOrganizationSerializer, ChristianMensOrganizationSerializer
            )    
from apps.profilesOrg.mixins.mixins import (
                SeniorPastorMixin, PastorsMixin, AssistantPastorsMixin,
                TeachersMixin, DeaconsMixin, WorshipLeadersMixin, WorshipTeamMixin, CounselorsMixin,
                AuthorsMixin, FacultyMembersMixin,
                PartnerOrganizationsMixin
            )
from apps.profilesOrg.mixins.voting_mixins import (
                OwnerManageMixin, WithdrawalMixin, DeletionOrRestorationMixin,
                FullAccessAdminMixin, LimitedAccessAdminMixin, VotingStatusMixin
            )
from apps.notifications.models import Notification
from common.permissions import IsFullAccessAdmin
import logging


logger = logging.getLogger(__name__)


# ORGANIZATION MANEGER ViewSet -----------------------------------------------------------------------------
class OrganizationManagerViewSet(viewsets.ModelViewSet):
    queryset = OrganizationManager.objects.all()
    serializer_class = OrganizationManagerSerializer
    permission_classes = [IsAuthenticated]

    # Filtering managers by organization
    def get_queryset(self):
        organization_slug = self.request.query_params.get('organization_slug')
        if organization_slug:
            return OrganizationManager.objects.filter(organization__slug=organization_slug)
        return super().get_queryset()

    # Creating a new admin (Only by full access admins)
    def create(self, request, *args, **kwargs):
        # Checking if the current user is a full access admin
        if not OrganizationManager.objects.filter(member_profile__id=request.user.member.id, access_level=OrganizationManager.FULL_ACCESS).exists():
            return Response({"error": "Only full access admins can add new admins."}, status=status.HTTP_403_FORBIDDEN)

        # Validating access level (Prevents limited access admins from assigning full access)
        access_level = request.data.get('access_level')
        if access_level == OrganizationManager.FULL_ACCESS and not request.user.is_full_access_admin():
            return Response({"error": "Limited access admins cannot assign full access."}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # Updating an admin (With required access controls)
    def update(self, request, *args, **kwargs):
        organization_manager = self.get_object()
        if not OrganizationManager.objects.filter(member_profile__id=request.user.member.id, access_level=OrganizationManager.FULL_ACCESS).exists():
            return Response({"error": "Only full access admins can update the organization manager."}, status=status.HTTP_403_FORBIDDEN)        
        access_level = request.data.get('access_level')
        if access_level == OrganizationManager.FULL_ACCESS and not request.user.is_full_access_admin():
            return Response({"error": "Limited access admins cannot assign full access."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(organization_manager, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    # Managing registration date during creation
    def perform_create(self, serializer):
        serializer.save(register_date=timezone.now())

    # Deleting an admin (Only by full access admins)
    def destroy(self, request, *args, **kwargs):
        organization_manager = self.get_object()
        if not OrganizationManager.objects.filter(member_profile__id=request.user.member.id, access_level=OrganizationManager.FULL_ACCESS).exists():
            return Response({"error": "Only full access admins can remove admins."}, status=status.HTTP_403_FORBIDDEN)
        
        organization_manager.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ORGANIZATION ViewSet -----------------------------------------------------------------------------
class OrganizationViewSet(
                    viewsets.ModelViewSet, 
                    OwnerManageMixin, WithdrawalMixin, DeletionOrRestorationMixin, 
                    FullAccessAdminMixin, LimitedAccessAdminMixin, VotingStatusMixin
                ):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def create(self, request, *args, **kwargs):
        member = request.user.member  
        if not member.is_townlit_verified:
            return Response({"error": "You must verify your identity before creating an organization. Please upload your ID."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data['org_owners'] = [member.username]
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)        
        organization = serializer.instance
        OrganizationManager.objects.create(
            organization=organization,
            member=member,
            access_level=OrganizationManager.FULL_ACCESS,
            is_approved=True
        )
        if organization.org_owners.count() == 1:
            message = (
                f"Your organization '{organization.org_name}' currently has only one owner. "
                "It is recommended to add at least 3 owners for better management and to avoid issues in case your account is deactivated."
            )
            Notification.objects.create(
                user=member,
                message=message,
                notification_type='organization_management',
                link=f"/organizations/{organization.slug}/owners/"
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        # register date and initializing the reports count to 0
        serializer.save(register_date=timezone.now(), reports_count=0)
        
    def retrieve(self, request, *args, **kwargs):
        # If the organization is suspended, it will also be handled here.
        organization = self.get_object()
        member = request.user.member
        if organization.is_suspended:
            return Response({"error": "This organization is currently suspended."}, status=status.HTTP_403_FORBIDDEN)
        if member.id not in organization.org_owners.values_list('id', flat=True):
            return Response({"error": "You are not authorized to view this organization."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(organization)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if organization.is_suspended:
            return Response({"error": "This organization is currently suspended and cannot be updated."}, status=status.HTTP_403_FORBIDDEN)
        org_manager = OrganizationManager.objects.filter(
            organization=organization, 
            member_profile__username=member.username, 
            access_level=OrganizationManager.FULL_ACCESS, 
            is_approved=True
        ).first()
        if not org_manager:
            return Response({"error": "Only admins with full access can modify the organization profile."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if organization.is_suspended:
            return Response({"error": "This organization is currently suspended and cannot be updated."}, status=status.HTTP_403_FORBIDDEN)
        org_manager = OrganizationManager.objects.filter(
            organization=organization, 
            member_profile__username=member.username, 
            access_level=OrganizationManager.FULL_ACCESS, 
            is_approved=True
        ).first()
        if not org_manager:
            return Response({"error": "Only admins with full access can modify the organization profile."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        organization = self.get_object()
        if organization.is_suspended:
            return Response({"error": "This organization is currently suspended and cannot be deleted."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    # Access Admins Check
    def check_access(self, organization, member_username, required_access_level):
        admin = OrganizationManager.objects.filter(organization=organization, member_profile__username=member_username).first()
        if not admin or admin.access_level not in required_access_level:
            return False
        return True

    
# SERVICE ViewSet --------------------------------------------------------------------------------
class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsFullAccessAdmin]

    def get_queryset(self):
        # Filter Services based on service_type and organization_id
        service_type = self.request.query_params.get('service_type', None)
        organization_id = self.request.query_params.get('organization_id', None)
        queryset = super().get_queryset()
        user_orgs = self.request.user.organizations.all()

        if organization_id and organization_id in user_orgs.values_list('id', flat=True):
            queryset = queryset.filter(organizations__id=organization_id)
        else:
            queryset = queryset.filter(organizations__in=user_orgs)
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        return queryset


# CHURCH(ORG) ViewSet ---------------------------------------------------------------------------
class ChurchViewSet(
                viewsets.ModelViewSet,
                SeniorPastorMixin, PastorsMixin, AssistantPastorsMixin,
                TeachersMixin, DeaconsMixin, WorshipLeadersMixin, PartnerOrganizationsMixin
            ):
    queryset = Church.objects.all()
    serializer_class = ChurchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optionally filter based on the user’s organizations
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return Church.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        church = self.get_object()
        serializer = self.get_serializer(church)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Ensure the user is a member of the organization creating the church
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a church for organization {member.organization.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        church = self.get_object()
        member = request.user.member
        if member not in church.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on church {church.name}")
            return Response({"error": "Only church owners can update the church."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated church {church.name}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        church = self.get_object()
        member = request.user.member
        if member not in church.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on church {church.name}")
            return Response({"error": "Only church owners can delete the church."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted church {church.name}")
        return super().destroy(request, *args, **kwargs)


# MISSION(ORG) ViewSet ---------------------------------------------------------------------------
class MissionOrganizationViewSet(
                            viewsets.ModelViewSet,
                            PartnerOrganizationsMixin
                        ):
    queryset = MissionOrganization.objects.all()
    serializer_class = MissionOrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optionally filter based on the user’s organizations
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return MissionOrganization.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        mission_organization = self.get_object()
        serializer = self.get_serializer(mission_organization)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Ensure the user is a member of the organization creating the mission organization
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a mission organization for {member.organization.org_name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        mission_organization = self.get_object()
        member = request.user.member
        if member not in mission_organization.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on mission organization {mission_organization.organization.org_name}")
            return Response({"error": "Only mission organization owners can update the mission organization."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated mission organization {mission_organization.organization.org_name}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        mission_organization = self.get_object()
        member = request.user.member
        if member not in mission_organization.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on mission organization {mission_organization.organization.org_name}")
            return Response({"error": "Only mission organization owners can delete the mission organization."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted mission organization {mission_organization.organization.org_name}")
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN PUBLISHING HOUSE(ORG) ViewSet ---------------------------------------------------------------------------
class ChristianPublishingHouseViewSet(
        viewsets.ModelViewSet,
        PartnerOrganizationsMixin, AuthorsMixin
    ):
    queryset = ChristianPublishingHouse.objects.all()
    serializer_class = ChristianPublishingHouseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianPublishingHouse.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        publishing_house = self.get_object()
        serializer = self.get_serializer(publishing_house)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a Christian Publishing House for organization {member.organization.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        publishing_house = self.get_object()
        member = request.user.member
        if member not in publishing_house.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on publishing house {publishing_house.custom_service_name or 'Christian Publishing House'}")
            return Response({"error": "Only publishing house owners can update this entity."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated publishing house {publishing_house.custom_service_name or 'Christian Publishing House'}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        publishing_house = self.get_object()
        member = request.user.member
        if member not in publishing_house.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on publishing house {publishing_house.custom_service_name or 'Christian Publishing House'}")
            return Response({"error": "Only publishing house owners can delete this entity."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted publishing house {publishing_house.custom_service_name or 'Christian Publishing House'}")
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN COUNSELING CENTER(ORG) ViewSet --------------------------------------------------------------------------
class ChristianCounselingCenterViewSet(
                viewsets.ModelViewSet,
                CounselorsMixin, PartnerOrganizationsMixin
            ):
    queryset = ChristianCounselingCenter.objects.all()
    serializer_class = ChristianCounselingCenterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # فیلتر بر اساس سازمان‌های کاربر
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianCounselingCenter.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        counseling_center = self.get_object()
        serializer = self.get_serializer(counseling_center)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a Christian Counseling Center for organization {member.organization.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        counseling_center = self.get_object()
        member = request.user.member
        if member not in counseling_center.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on Christian Counseling Center {counseling_center}")
            return Response({"error": "Only organization owners can update the counseling center."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated Christian Counseling Center {counseling_center}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        counseling_center = self.get_object()
        member = request.user.member
        if member not in counseling_center.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on Christian Counseling Center {counseling_center}")
            return Response({"error": "Only organization owners can delete the counseling center."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted Christian Counseling Center {counseling_center}")
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN SERVISES CENTER(ORG) ViewSet
class CounselingServiceViewSet(viewsets.ModelViewSet, CounselorsMixin):
    queryset = CounselingService.objects.all()
    serializer_class = CounselingServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return CounselingService.objects.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        service = self.get_object()
        serializer = self.get_serializer(service)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a counseling service.")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        service = self.get_object()
        serializer = self.get_serializer(service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        logger.info(f"User {request.user.username} updated counseling service {service.service_name}.")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        service = self.get_object()
        self.perform_destroy(service)
        logger.info(f"User {request.user.username} deleted counseling service {service.service_name}.")
        return Response(status=status.HTTP_204_NO_CONTENT)


# CHRISTIAN WORSHIP MINISTRY(ORG) ViewSet ---------------------------------------------------------------------------------
class ChristianWorshipMinistryViewSet(
                viewsets.ModelViewSet,
                WorshipLeadersMixin, WorshipTeamMixin, PartnerOrganizationsMixin,
            ):
    queryset = ChristianWorshipMinistry.objects.all()
    serializer_class = ChristianWorshipMinistrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianWorshipMinistry.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        worship_ministry = self.get_object()
        serializer = self.get_serializer(worship_ministry)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a Christian Worship Ministry for organization {member.organization.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        worship_ministry = self.get_object()
        member = request.user.member
        if member not in worship_ministry.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on Christian Worship Ministry {worship_ministry}")
            return Response({"error": "Only organization owners can update the ministry."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated Christian Worship Ministry {worship_ministry}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        worship_ministry = self.get_object()
        member = request.user.member
        if member not in worship_ministry.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on Christian Worship Ministry {worship_ministry}")
            return Response({"error": "Only organization owners can delete the ministry."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted Christian Worship Ministry {worship_ministry}")
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN CONFERENCE CENTER(ORG) ViewSet ---------------------------------------------------------------------------
class ChristianConferenceCenterViewSet(
        viewsets.ModelViewSet,
        PartnerOrganizationsMixin
    ):
    queryset = ChristianConferenceCenter.objects.all()
    serializer_class = ChristianConferenceCenterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianConferenceCenter.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        conference_center = self.get_object()
        serializer = self.get_serializer(conference_center)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created a conference center for organization {member.organization.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        conference_center = self.get_object()
        member = request.user.member
        if member not in conference_center.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on conference center {conference_center.custom_service_name}")
            return Response({"error": "Only organization owners can update the conference center."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated conference center {conference_center.custom_service_name}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        conference_center = self.get_object()
        member = request.user.member
        if member not in conference_center.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on conference center {conference_center.custom_service_name}")
            return Response({"error": "Only organization owners can delete the conference center."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted conference center {conference_center.custom_service_name}")
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN EDUCATIONAL IINSTITUTION(ORG) ViewSet ---------------------------------------------------------------------------
class ChristianEducationalInstitutionViewSet(
        viewsets.ModelViewSet,
        FacultyMembersMixin, PartnerOrganizationsMixin
    ):
    queryset = ChristianEducationalInstitution.objects.all()
    serializer_class = ChristianEducationalInstitutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianEducationalInstitution.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        institution = self.get_object()
        serializer = self.get_serializer(institution)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        logger.info(f"User {request.user.username} created an educational institution for organization {member.organization.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        institution = self.get_object()
        member = request.user.member
        if member not in institution.organization.org_owners.all():
            logger.warning(f"Unauthorized update attempt by {request.user.username} on institution {institution.custom_service_name}")
            return Response({"error": "Only organization owners can update the institution."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} updated institution {institution.custom_service_name}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        institution = self.get_object()
        member = request.user.member
        if member not in institution.organization.org_owners.all():
            logger.warning(f"Unauthorized delete attempt by {request.user.username} on institution {institution.custom_service_name}")
            return Response({"error": "Only organization owners can delete the institution."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"User {request.user.username} deleted institution {institution.custom_service_name}")
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN CHILDREN ORGANIZATION(ORG) ViewSet ---------------------------------------------------------------------------
class ChristianChildrenOrganizationViewSet(
        viewsets.ModelViewSet,
        PartnerOrganizationsMixin, TeachersMixin
    ):
    queryset = ChristianChildrenOrganization.objects.all()
    serializer_class = ChristianChildrenOrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optional filtering based on user's organizations
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianChildrenOrganization.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        organization = self.get_object()
        serializer = self.get_serializer(organization)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Ensure the user is part of the organization creating the children organization
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can update this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can delete this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN YOUTH ORGANIZATION(ORG) ViewSet ------------------------------------------------------------------------------
class ChristianYouthOrganizationViewSet(
        viewsets.ModelViewSet,
        PastorsMixin, AssistantPastorsMixin, TeachersMixin, PartnerOrganizationsMixin
    ):
    queryset = ChristianYouthOrganization.objects.all()
    serializer_class = ChristianYouthOrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optional filtering based on user's organizations
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianYouthOrganization.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        organization = self.get_object()
        serializer = self.get_serializer(organization)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Ensure the user is part of the organization creating the youth organization
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can update this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can delete this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


# CHRISTIAN WOMENS ORGANIZATION(ORG) ViewSet -----------------------------------------------------------------------------
class ChristianWomensOrganizationViewSet(
        viewsets.ModelViewSet,
        PastorsMixin, AssistantPastorsMixin, PartnerOrganizationsMixin
    ):
    queryset = ChristianWomensOrganization.objects.all()
    serializer_class = ChristianWomensOrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optional filtering based on user's organizations
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianWomensOrganization.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        organization = self.get_object()
        serializer = self.get_serializer(organization)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # Ensure the user is part of the organization creating the women's organization
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can update this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can delete this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)
    
    
# CHRISTIAN MENS ORGANIZATION(ORG) ViewSet -------------------------------------------------------------------------------
class ChristianMensOrganizationViewSet(
        viewsets.ModelViewSet,
        PastorsMixin, AssistantPastorsMixin, PartnerOrganizationsMixin
    ):
    queryset = ChristianMensOrganization.objects.all()
    serializer_class = ChristianMensOrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return ChristianMensOrganization.objects.filter(organization__org_owners=user.member)

    def retrieve(self, request, *args, **kwargs):
        organization = self.get_object()
        serializer = self.get_serializer(organization)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = request.user.member
        data = request.data.copy()
        data['organization'] = member.organization.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def update(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can update this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        organization = self.get_object()
        member = request.user.member
        if member not in organization.organization.org_owners.all():
            return Response({"error": "Only owners can delete this organization."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


