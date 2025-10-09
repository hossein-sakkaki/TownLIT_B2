from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated


from apps.profiles.models import Member
from apps.profilesOrg.models import Organization
from apps.posts.serializers import SimpleOrganizationSerializer, SimpleCustomUserSerializer
from apps.profiles.serializers_min import SimpleMemberSerializer
from common.permissions import IsFullAccessAdmin
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# SENIOR PASTOR Mixin -------------------------------------------------------------------------------------------
class SeniorPastorMixin:
    # Mixin to manage the senior pastor (ForeignKey)
    @action(detail=True, methods=['get'], url_path='get-senior-pastor', permission_classes=[IsAuthenticated])
    def get_senior_pastor(self, request, pk=None):
        item = self.get_object()
        pastor = item.senior_pastors
        if pastor:
            serializer = SimpleMemberSerializer(pastor)
            return Response({"senior_pastor": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic 
    @action(detail=True, methods=['post'], url_path='assign-senior-pastor', permission_classes=[IsFullAccessAdmin])
    def assign_senior_pastor(self, request, pk=None):
        item = self.get_object()
        pastor_id = request.data.get('pastor_id')
        try:
            pastor = Member.objects.get(id=pastor_id)
            item.senior_pastors = pastor
            item.save()
            return Response({"message": "Senior pastor assigned successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-senior-pastor', permission_classes=[IsFullAccessAdmin])
    def remove_senior_pastor(self, request, pk=None):
        item = self.get_object()
        if item.senior_pastors is None:
            return Response({"message": "No senior pastor assigned to remove."}, status=status.HTTP_400_BAD_REQUEST)
        item.senior_pastors = None
        item.save()
        return Response({"message": "Senior pastor removed successfully."}, status=status.HTTP_200_OK)


# PASTOR Mixin -------------------------------------------------------------------------------------------
class PastorsMixin:
    # Mixin to manage pastors in a ManyToMany field   
    @action(detail=True, methods=['get'], url_path='list-pastors', permission_classes=[IsAuthenticated])
    def list_pastors(self, request, pk=None):
        item = self.get_object()
        pastors = item.pastors.all()
        if pastors.exists():
            serializer = SimpleMemberSerializer(pastors, many=True)
            return Response({"pastors": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='assign-pastor', permission_classes=[IsFullAccessAdmin])
    def assign_pastor(self, request, pk=None):
        item = self.get_object()
        pastor_username = request.data.get('pastor_username')
        try:
            pastor = Member.objects.get(username=pastor_username)
            item.pastors.add(pastor)
            item.save()
            serializer = SimpleMemberSerializer(pastor)
            return Response({"message": "Pastor assigned successfully.", "pastor": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-pastor', permission_classes=[IsFullAccessAdmin])
    def remove_pastor(self, request, pk=None):
        item = self.get_object()
        pastor_username = request.data.get('pastor_username')
        try:
            pastor = Member.objects.get(username=pastor_username)
            if not item.pastors.filter(username=pastor_username).exists():
                return Response({"message": "This pastor is not assigned to this organization."}, status=status.HTTP_400_BAD_REQUEST)
            item.pastors.remove(pastor)
            item.save()
            return Response({"message": "Pastor removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        

# ASSISTANT PASTOR Mixin -----------------------------------------------------------------------------------------
class AssistantPastorsMixin:
    # Mixin to manage assistant pastors in a ManyToMany field
    @action(detail=True, methods=['get'], url_path='list-assistant-pastors', permission_classes=[IsAuthenticated])
    def list_assistant_pastors(self, request, pk=None):
        item = self.get_object()
        assistant_pastors = item.assistant_pastors.all()
        if assistant_pastors.exists():
            serializer = SimpleMemberSerializer(assistant_pastors, many=True)
            return Response({"assistant_pastors": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='assign-assistant-pastor', permission_classes=[IsFullAccessAdmin])
    def assign_assistant_pastor(self, request, pk=None):
        item = self.get_object()
        assistant_pastor_username = request.data.get('assistant_pastor_username')
        try:
            assistant_pastor = Member.objects.get(username=assistant_pastor_username)
            item.assistant_pastors.add(assistant_pastor)
            item.save()
            serializer = SimpleMemberSerializer(assistant_pastor)
            return Response({"message": "Assistant pastor assigned successfully.", "assistant_pastor": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-assistant-pastor', permission_classes=[IsFullAccessAdmin])
    def remove_assistant_pastor(self, request, pk=None):
        item = self.get_object()
        assistant_pastor_username = request.data.get('assistant_pastor_username')
        try:
            assistant_pastor = Member.objects.get(username=assistant_pastor_username)
            if not item.assistant_pastors.filter(username=assistant_pastor_username).exists():
                return Response({"message": "This assistant pastor is not assigned to this organization."}, status=status.HTTP_400_BAD_REQUEST)
            item.assistant_pastors.remove(assistant_pastor)
            item.save()
            return Response({"message": "Assistant pastor removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        

# TEACHER Mixin -------------------------------------------------------------------------------------------
class TeachersMixin:
    # Mixin to manage teachers in a ManyToMany field
    @action(detail=True, methods=['get'], url_path='list-teachers', permission_classes=[IsAuthenticated])
    def list_teachers(self, request, pk=None):
        item = self.get_object()
        teachers = item.teachers.all()
        if teachers.exists():
            serializer = SimpleMemberSerializer(teachers, many=True)
            return Response({"teachers": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='assign-teacher', permission_classes=[IsFullAccessAdmin])
    def assign_teacher(self, request, pk=None):
        item = self.get_object()
        teacher_username = request.data.get('teacher_username')
        try:
            teacher = Member.objects.get(username=teacher_username)
            item.teachers.add(teacher)
            item.save()
            serializer = SimpleMemberSerializer(teacher)
            return Response({"message": "Teacher assigned successfully.", "teacher": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-teacher', permission_classes=[IsFullAccessAdmin])
    def remove_teacher(self, request, pk=None):
        item = self.get_object()
        teacher_username = request.data.get('teacher_username')
        try:
            teacher = Member.objects.get(username=teacher_username)
            if not item.teachers.filter(username=teacher_username).exists():
                return Response({"message": "This teacher is not assigned to this organization."}, status=status.HTTP_400_BAD_REQUEST)

            item.teachers.remove(teacher)
            item.save()
            return Response({"message": "Teacher removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        
# DEACONS Mixin -------------------------------------------------------------------------------------------
class DeaconsMixin:
    # Mixin to manage deacons in a ManyToMany field
    @action(detail=True, methods=['get'], url_path='list-deacons', permission_classes=[IsAuthenticated])
    def list_deacons(self, request, pk=None):
        item = self.get_object()
        deacons = item.deacons.all()
        if deacons.exists():
            serializer = SimpleMemberSerializer(deacons, many=True)
            return Response({"deacons": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='assign-deacon', permission_classes=[IsFullAccessAdmin])
    def assign_deacon(self, request, pk=None):
        item = self.get_object()
        deacon_username = request.data.get('deacon_username')
        try:
            deacon = Member.objects.get(username=deacon_username)
            item.deacons.add(deacon)
            item.save()
            serializer = SimpleMemberSerializer(deacon)
            return Response({"message": "Deacon assigned successfully.", "deacon": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='remove-deacon', permission_classes=[IsFullAccessAdmin])
    def remove_deacon(self, request, pk=None):
        item = self.get_object()
        deacon_username = request.data.get('deacon_username')
        try:
            deacon = Member.objects.get(username=deacon_username)
            if not item.deacons.filter(username=deacon_username).exists():
                return Response({"message": "This deacon is not assigned to this organization."}, status=status.HTTP_400_BAD_REQUEST)
            item.deacons.remove(deacon)
            item.save()
            return Response({"message": "Deacon removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        

# WORSHIP LEADER Mixin -------------------------------------------------------------------------------------------
class WorshipLeadersMixin:
    # Mixin to manage worship leaders in a ManyToMany field    
    @action(detail=True, methods=['get'], url_path='list-worship-leaders', permission_classes=[IsAuthenticated])
    def list_worship_leaders(self, request, pk=None):
        item = self.get_object()
        worship_leaders = item.worship_leaders.all()
        if worship_leaders.exists():
            serializer = SimpleMemberSerializer(worship_leaders, many=True)
            return Response({"worship_leaders": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='assign-worship-leader', permission_classes=[IsFullAccessAdmin])
    def assign_worship_leader(self, request, pk=None):
        item = self.get_object()
        leader_username = request.data.get('leader_username')
        try:
            leader = Member.objects.get(username=leader_username)
            item.worship_leaders.add(leader)
            item.save()
            serializer = SimpleMemberSerializer(leader)
            return Response({"message": "Worship leader assigned successfully.", "worship_leader": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-worship-leader', permission_classes=[IsFullAccessAdmin])
    def remove_worship_leader(self, request, pk=None):
        item = self.get_object()
        leader_username = request.data.get('leader_username')
        try:
            leader = Member.objects.get(username=leader_username)
            if not item.worship_leaders.filter(username=leader_username).exists():
                return Response({"message": "This worship leader is not assigned to this organization."}, status=status.HTTP_400_BAD_REQUEST)

            item.worship_leaders.remove(leader)
            item.save()
            return Response({"message": "Worship leader removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)



# WORSHIP TEAM Mixin -------------------------------------------------------------------------------------------
class WorshipTeamMixin:
    @action(detail=True, methods=['get'], url_path='list-worship-team', permission_classes=[IsAuthenticated])
    def list_worship_team(self, request, pk=None):
        ministry = self.get_object()
        worship_team = ministry.worship_team.all()
        if worship_team.exists():
            serializer = SimpleMemberSerializer(worship_team, many=True)
            return Response({"worship_team": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='add-worship-team-member', permission_classes=[IsFullAccessAdmin])
    def add_worship_team_member(self, request, pk=None):
        ministry = self.get_object()
        member_username = request.data.get('member_username')
        try:
            member = Member.objects.get(username=member_username)
            ministry.worship_team.add(member)
            ministry.save()
            serializer = SimpleMemberSerializer(member)
            return Response({"message": "Worship team member added successfully.", "member": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-worship-team-member', permission_classes=[IsFullAccessAdmin])
    def remove_worship_team_member(self, request, pk=None):
        ministry = self.get_object()
        member_username = request.data.get('member_username')
        try:
            member = Member.objects.get(username=member_username)
            if not ministry.worship_team.filter(username=member_username).exists():
                return Response({"message": "This member is not part of the worship team."}, status=status.HTTP_400_BAD_REQUEST)
            ministry.worship_team.remove(member)
            ministry.save()
            return Response({"message": "Worship team member removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


# AUTHOR Mixin -------------------------------------------------------------------------------------------
class AuthorsMixin:
    @action(detail=True, methods=['get'], url_path='list-authors', permission_classes=[IsAuthenticated])
    def list_authors(self, request, pk=None):
        publishing_house = self.get_object()
        authors = publishing_house.authors.all()
        if not authors.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = SimpleCustomUserSerializer(authors, many=True)
        return Response({"authors": serializer.data}, status=status.HTTP_200_OK)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='add-author', permission_classes=[IsFullAccessAdmin])
    def add_author(self, request, pk=None):
        publishing_house = self.get_object()
        author_username = request.data.get('author_username')
        try:
            author = CustomUser.objects.get(username=author_username)
            publishing_house.authors.add(author)
            publishing_house.save()
            serializer = SimpleCustomUserSerializer(author)
            return Response({"message": "Author added successfully.", "author": serializer.data}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-author', permission_classes=[IsFullAccessAdmin])
    def remove_author(self, request, pk=None):
        publishing_house = self.get_object()
        author_username = request.data.get('author_username')
        try:
            author = CustomUser.objects.get(username=author_username)
            if not publishing_house.authors.filter(username=author_username).exists():
                return Response({"message": "This author is not part of this publishing house."}, status=status.HTTP_400_BAD_REQUEST)

            publishing_house.authors.remove(author)
            publishing_house.save()
            return Response({"message": "Author removed successfully."}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND) 


# COUNSELORS Mixin -------------------------------------------------------------------------------------------
class CounselorsMixin:
    @action(detail=True, methods=['get'], url_path='list-counselors', permission_classes=[IsAuthenticated])
    def list_counselors(self, request, pk=None):
        center = self.get_object()
        counselors = center.counselors.all()
        if not counselors.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        serializer = SimpleMemberSerializer(counselors, many=True)
        return Response({"counselors": serializer.data}, status=status.HTTP_200_OK)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='add-counselor', permission_classes=[IsFullAccessAdmin])
    def add_counselor(self, request, pk=None):
        center = self.get_object()
        counselor_username = request.data.get('counselor_username')
        try:
            counselor = Member.objects.get(username=counselor_username)
            center.counselors.add(counselor)
            center.save()
            serializer = SimpleMemberSerializer(counselor)
            return Response({"message": "Counselor added successfully.", "counselor": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-counselor', permission_classes=[IsFullAccessAdmin])
    def remove_counselor(self, request, pk=None):
        center = self.get_object()
        counselor_username = request.data.get('counselor_username')
        try:
            counselor = Member.objects.get(username=counselor_username)
            if not center.counselors.filter(username=counselor_username).exists():
                return Response({"message": "This counselor is not assigned to this center."}, status=status.HTTP_400_BAD_REQUEST)

            center.counselors.remove(counselor)
            center.save()
            return Response({"message": "Counselor removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


# FACULTY Mixin -------------------------------------------------------------------------------------------
class FacultyMembersMixin:
    # List Faculty Members
    @action(detail=True, methods=['get'], url_path='list-faculty-members', permission_classes=[IsAuthenticated])
    def list_faculty_members(self, request, pk=None):
        institution = self.get_object()
        faculty_members = institution.in_town_faculty.all()
        if faculty_members.exists():
            serializer = SimpleMemberSerializer(faculty_members, many=True)
            return Response({"faculty_members": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)

    # Add Faculty Member
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='add-faculty-member', permission_classes=[IsFullAccessAdmin])
    def add_faculty_member(self, request, pk=None):
        institution = self.get_object()
        faculty_username = request.data.get('faculty_username')
        try:
            faculty_member = Member.objects.get(username=faculty_username)
            institution.in_town_faculty.add(faculty_member)
            institution.save()
            serializer = SimpleMemberSerializer(faculty_member)
            return Response({"message": "Faculty member added successfully.", "faculty_member": serializer.data}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-faculty-member', permission_classes=[IsFullAccessAdmin])
    def remove_faculty_member(self, request, pk=None):
        institution = self.get_object()
        faculty_username = request.data.get('faculty_username')
        try:
            faculty_member = Member.objects.get(username=faculty_username)
            if not institution.in_town_faculty.filter(username=faculty_username).exists():
                return Response({"message": "This faculty member is not assigned to this institution."}, status=status.HTTP_400_BAD_REQUEST)
            institution.in_town_faculty.remove(faculty_member)
            institution.save()
            return Response({"message": "Faculty member removed successfully."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        
# PARTNER ORGANIZATIONS Mixin -------------------------------------------------------------------------------------------
class PartnerOrganizationsMixin:
    @action(detail=True, methods=['get'], url_path='list-partner-organizations', permission_classes=[IsAuthenticated])
    def list_partner_organizations(self, request, pk=None):
        item = self.get_object()
        partners = item.partner_organizations.all()
        if partners.exists():
            serializer = SimpleOrganizationSerializer(partners, many=True)
            return Response({"partner_organizations": serializer.data}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='add-partner-organization', permission_classes=[IsFullAccessAdmin])
    def add_partner_organization(self, request, pk=None):
        item = self.get_object()
        organization_name = request.data.get('organization_name')
        try:
            organization = Organization.objects.get(org_name=organization_name)
            item.partner_organizations.add(organization)
            item.save()
            serializer = SimpleOrganizationSerializer(organization)
            return Response({"message": "Partner organization added successfully.", "organization": serializer.data}, status=status.HTTP_200_OK)
        except Organization.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='remove-partner-organization', permission_classes=[IsFullAccessAdmin])
    def remove_partner_organization(self, request, pk=None):
        item = self.get_object()
        organization_name = request.data.get('organization_name')
        try:
            organization = Organization.objects.get(org_name=organization_name)
            if not item.partner_organizations.filter(org_name=organization_name).exists():
                return Response({"message": "This organization is not a partner."}, status=status.HTTP_400_BAD_REQUEST)
            item.partner_organizations.remove(organization)
            item.save()
            return Response({"message": "Partner organization removed successfully."}, status=status.HTTP_200_OK)
        except Organization.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)



