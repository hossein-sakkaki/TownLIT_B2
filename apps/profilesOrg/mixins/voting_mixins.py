from django.utils import timezone
from django.db import transaction

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status

from apps.profiles.models import Member
from apps.profilesOrg.models import OrganizationManager, VotingHistory
from common.permissions import IsFullAccessAdmin

import logging
logger = logging.getLogger(__name__)



# ADD or REMOVE OWNER Mixin -----------------------------------------------------------------------------
class OwnerManageMixin:
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def request_add_owner(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user.username not in organization.org_owners.values_list('username', flat=True):
            return Response({"error": "Only owners can request adding a new owner."}, status=status.HTTP_403_FORBIDDEN)
        new_owner_username = request.data.get('member_username')
        try:
            new_owner = Member.objects.get(username=new_owner_username)
            if not new_owner.is_verified_identity:
                return Response({"error": f"User {new_owner.username} must verify their identity before being added as an owner."}, status=status.HTTP_403_FORBIDDEN)
            if new_owner.username in organization.org_owners.values_list('username', flat=True):
                return Response({"error": "This member is already an owner."}, status=status.HTTP_400_BAD_REQUEST)
            voting_history = VotingHistory.objects.create(
                organization=organization,
                voting_type='owner_addition',
                votes_required=(organization.org_owners.count() // 2) + 1,
                description=f"Request to add {new_owner.username} as owner."
            )
            voting_history.voted_users.add(user)
            organization.new_owner_request = new_owner
            organization.save()
            logger.info(f"User {user.username} requested to add new owner {new_owner.username} to organization {organization.slug}")
            return Response({"message": "Request for adding a new owner has been made. Other owners must approve."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            logger.error(f"Member {new_owner_username} not found while trying to add as owner")
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        
    # Vote For Add New Owner
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote_for_add_owner(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user.username not in organization.org_owners.values_list('username', flat=True):
            return Response({"error": "Only owners can vote for adding a new owner."}, status=status.HTTP_403_FORBIDDEN)
        if not organization.new_owner_request:
            return Response({"error": "No new owner request is pending."}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve the voting history entry
        voting_history = VotingHistory.objects.filter(organization=organization, voting_type='owner_addition').latest('created_at')
        if user.username in voting_history.voted_users.values_list('username', flat=True):
            return Response({"message": "You have already voted."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history.voted_users.add(user)
        if voting_history.voted_users.count() >= voting_history.votes_required:
            organization.org_owners.add(organization.new_owner_request)
            organization.new_owner_request = None
            voting_history.result = 'approved'
            organization.save()
            logger.info(f"New owner added to organization {organization.slug}")
            return Response({"message": "New owner added successfully."}, status=status.HTTP_202_ACCEPTED)
        else:
            voting_history.save()
            return Response({"message": "Vote recorded. Awaiting more votes."}, status=status.HTTP_200_OK)

    # Remove Owner
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def request_owner_removal(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        owner_to_remove_username = request.data.get('owner_username')
        if user.username not in organization.org_owners.values_list('username', flat=True):
            return Response({"error": "Only owners can request removal."}, status=status.HTTP_403_FORBIDDEN)
        if organization.owner_removal_request:
            return Response({"error": "There is already a pending removal request."}, status=status.HTTP_400_BAD_REQUEST)
        if organization.org_owners.count() == 1:
            return Response({"error": "Cannot remove the last remaining owner. Organization must have at least one owner."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            owner_to_remove = Member.objects.get(username=owner_to_remove_username)
            if owner_to_remove.username not in organization.org_owners.values_list('username', flat=True):
                return Response({"error": "This user is not an owner."}, status=status.HTTP_400_BAD_REQUEST)
            voting_history = VotingHistory.objects.create(
                organization=organization,
                voting_type='owner_removal',
                votes_required=(organization.org_owners.count() // 2) + 1,
                description=f"Request to remove owner {owner_to_remove.username}."
            )
            voting_history.voted_users.add(user)
            organization.owner_removal_request = owner_to_remove
            organization.save()
            logger.info(f"User {user.username} requested removal of owner {owner_to_remove.username} from organization {organization.slug}")
            return Response({"message": "Removal request made. Other owners must approve."}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            logger.error(f"Owner {owner_to_remove_username} not found for removal in organization {organization.slug}")
            return Response({"error": "Owner not found."}, status=status.HTTP_404_NOT_FOUND)

    # Vote for Removal Owner
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote_for_removal(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member        
        if user.username not in organization.org_owners.values_list('username', flat=True):
            return Response({"error": "Only owners can vote for removal."}, status=status.HTTP_403_FORBIDDEN)
        if not organization.owner_removal_request:
            return Response({"error": "No removal request is pending."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history = VotingHistory.objects.filter(organization=organization, voting_type='owner_removal').latest('created_at')
        if user.username in voting_history.voted_users.values_list('username', flat=True):
            return Response({"message": "You have already voted."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history.voted_users.add(user)        
        if voting_history.voted_users.count() >= voting_history.votes_required:
            organization.org_owners.remove(organization.owner_removal_request)
            organization.owner_removal_request = None
            voting_history.result = 'approved'
            organization.save()
            logger.info(f"Owner {organization.owner_removal_request.username} removed from organization {organization.slug}")
            return Response({"message": "Owner has been removed."}, status=status.HTTP_200_OK)
        else:
            voting_history.save()
            return Response({"message": "Vote recorded. Awaiting more votes."}, status=status.HTTP_200_OK)


# WITHDRAWAL OWNER Mixin ---------------------------------------------------------------------------------------
class WithdrawalMixin:
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def request_owner_withdrawal(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user not in organization.org_owners.all():
            return Response({"error": "Only owners can request withdrawal."}, status=status.HTTP_403_FORBIDDEN)
        
        voting_history = VotingHistory.objects.create(
            organization=organization,
            voting_type='withdrawal',
            votes_required=(organization.org_owners.count() // 2) + 1,
            description=f"Request for {user.username} to withdraw from ownership."
        )
        voting_history.voted_users.add(user)
        organization.owner_withdrawal_request = user
        organization.save()

        logger.info(f"User {user.username} requested to withdraw from ownership of organization {organization.slug}")
        return Response({"message": "Withdrawal request made. Other owners must approve."}, status=status.HTTP_200_OK)

    # Vote For Withdrawal Owner
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote_for_withdrawal(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user not in organization.org_owners.all():
            return Response({"error": "Only owners can vote for withdrawal."}, status=status.HTTP_403_FORBIDDEN)
        if not organization.owner_withdrawal_request:
            return Response({"error": "No withdrawal request is pending."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history = VotingHistory.objects.filter(organization=organization, voting_type='withdrawal').latest('created_at')
        if user.username in voting_history.voted_users.values_list('username', flat=True):
            return Response({"message": "You have already voted."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history.voted_users.add(user)
        if voting_history.voted_users.count() >= voting_history.votes_required:
            organization.org_owners.remove(organization.owner_withdrawal_request)
            voting_history.result = 'approved'
            organization.owner_withdrawal_request = None
            organization.save()
            logger.info(f"Owner {user.username} has withdrawn from ownership of organization {organization.slug}")
            return Response({"message": "Owner has successfully withdrawn."}, status=status.HTTP_200_OK)
        else:
            voting_history.save()
            return Response({"message": "Vote recorded. Awaiting more votes."}, status=status.HTTP_200_OK)


# DELETION or RESTORATION ORGANIZATION Mixin ---------------------------------------------------------------------------------
class DeletionOrRestorationMixin:
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def request_deletion(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user not in organization.org_owners.all():
            return Response({"error": "Only owners can request deletion."}, status=status.HTTP_403_FORBIDDEN)
        if organization.deletion_requested_at:
            return Response({"error": "Deletion request is already pending."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history = VotingHistory.objects.create(
            organization=organization,
            voting_type='deletion',
            votes_required=(organization.org_owners.count() // 2) + 1,
            description=f"Request for deletion of organization {organization.org_name}."
        )
        voting_history.voted_users.add(user)
        organization.deletion_requested_at = timezone.now()
        organization.save()
        logger.info(f"User {user.username} requested deletion of organization {organization.slug}")
        return Response({"message": "Deletion request has been made. Other owners must approve."}, status=status.HTTP_200_OK)

    # Vote For Deletion Request
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote_for_deletion(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user.username not in organization.org_owners.values_list('username', flat=True):
            return Response({"error": "Only owners can approve deletion."}, status=status.HTTP_403_FORBIDDEN)
        if not organization.deletion_requested_at:
            return Response({"error": "No deletion request is pending."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history = VotingHistory.objects.filter(organization=organization, voting_type='deletion').latest('created_at')
        if user.username in voting_history.voted_users.values_list('username', flat=True):
            return Response({"message": "You have already voted."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history.voted_users.add(user)
        if voting_history.voted_users.count() >= voting_history.votes_required:
            organization.is_active = False
            organization.save()
            voting_history.result = 'approved'
            voting_history.completed_at = timezone.now()
            voting_history.save()
            logger.info(f"Organization {organization.slug} has been marked for deletion")
            return Response({"message": "Organization deletion confirmed. Organization will be deleted in 90 days if not restored."}, status=status.HTTP_202_ACCEPTED)
        return Response({"message": "Deletion approval recorded. Awaiting more votes."}, status=status.HTTP_200_OK)
    
    # Vote For Restoration Request
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote_for_restoration(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user not in organization.org_owners.all():
            return Response({"error": "Only owners can vote for restoration."}, status=status.HTTP_403_FORBIDDEN)
        if not organization.deletion_requested_at:
            return Response({"error": "No deletion request is pending."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history = VotingHistory.objects.filter(organization=organization, voting_type='restoration').latest('created_at')
        if user in voting_history.voted_users.all():
            return Response({"message": "You have already voted."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history.voted_users.add(user)
        if voting_history.voted_users.count() >= voting_history.votes_required:
            organization.is_active = True
            organization.deletion_requested_at = None
            organization.save()
            voting_history.result = 'approved'
            voting_history.completed_at = timezone.now()
            voting_history.save()
            logger.info(f"Organization {organization.slug} has been restored to active status")
            return Response({"message": "Organization has been restored."}, status=status.HTTP_202_ACCEPTED)
        return Response({"message": "Restoration vote recorded. Awaiting more votes."}, status=status.HTTP_200_OK)


# FULL ACCESS ADMIN Mixin ---------------------------------------------------------------------------------
class FullAccessAdminMixin:
    # Propose Admin Replacement
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def propose_admin_replacement(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user not in organization.org_owners.all():
            return Response({"error": "Only owners can propose admin replacement."}, status=status.HTTP_403_FORBIDDEN)
        new_admin_username = request.data.get('member_username')
        try:
            new_admin = Member.objects.get(username=new_admin_username)
            if OrganizationManager.objects.filter(organization=organization, member=new_admin).exists():
                return Response({"error": "This member is already an admin."}, status=status.HTTP_400_BAD_REQUEST)            
        except Member.DoesNotExist:
            return Response({"error": "Member not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Setting the current admin to replacing mode
        current_admin = OrganizationManager.objects.filter(organization=organization, access_level=OrganizationManager.FULL_ACCESS).first()
        if not current_admin:
            return Response({"error": "No current full admin found."}, status=status.HTTP_404_NOT_FOUND)
        current_admin.is_being_replaced = True
        current_admin.save()
        voting_history = VotingHistory.objects.create(
            organization=organization,
            voting_type='admin_replacement',
            votes_required=(organization.org_owners.count() // 2) + 1,
            description=f"Proposal to replace admin with {new_admin.username}."
        )
        voting_history.voted_users.add(user)
        organization.proposed_admin = new_admin
        organization.save()
        logger.info(f"User {user.username} proposed admin replacement with {new_admin.username} in organization {organization.slug}")
        return Response({"message": "Admin replacement process started. Voting is required."}, status=status.HTTP_200_OK)


    # Vote For Admin Replacement
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote_for_admin_replacement(self, request, pk=None):
        organization = self.get_object()
        user = request.user.member
        if user not in organization.org_owners.all():
            return Response({"error": "Only owners can vote for admin replacement."}, status=status.HTTP_403_FORBIDDEN)
        if not organization.proposed_admin:
            return Response({"error": "No admin replacement proposal found."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history = VotingHistory.objects.filter(
            organization=organization, voting_type='admin_replacement'
        ).latest('created_at')
        if user in voting_history.voted_users.all():
            return Response({"error": "You have already voted."}, status=status.HTTP_400_BAD_REQUEST)
        voting_history.voted_users.add(user)
        if voting_history.voted_users.count() >= voting_history.votes_required:
            try:
                # Delete old admin
                current_admin = OrganizationManager.objects.get(
                    organization=organization, 
                    access_level=OrganizationManager.FULL_ACCESS, 
                    is_being_replaced=True
                )
                current_admin.delete()
                
                # Create new admin
                new_admin, created = OrganizationManager.objects.get_or_create(
                    organization=organization, 
                    member=organization.proposed_admin
                )
                new_admin.access_level = OrganizationManager.FULL_ACCESS
                new_admin.is_approved = True
                new_admin.save()

                organization.is_suspended = False
                organization.proposed_admin = None
                organization.save()
                
                voting_history.result = 'approved'
                voting_history.completed_at = timezone.now()
                voting_history.save()
                organization.save()
                logger.info(f"Admin {new_admin.member.username} has replaced the previous admin in organization {organization.slug}")
                return Response({"message": "Admin replacement completed."}, status=status.HTTP_200_OK)
            except OrganizationManager.DoesNotExist:
                return Response({"error": "Current full access admin not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"message": "Your vote has been recorded. Awaiting more votes."}, status=status.HTTP_200_OK)


# LIMITED ACCESS ADMIN Mixin ---------------------------------------------------------------------------------
class LimitedAccessAdminMixin:
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin])
    def add_limited_access_admin(self, request, pk=None):
        organization = self.get_object()        
        user = request.user.member
        try:
            manager = OrganizationManager.objects.get(organization=organization, member=user)
            if manager.access_level != OrganizationManager.FULL_ACCESS:
                return Response({"error": "Only admins with full access can add new admins."}, status=status.HTTP_403_FORBIDDEN)
        except OrganizationManager.DoesNotExist:
            return Response({"error": "You are not an admin of this organization."}, status=status.HTTP_403_FORBIDDEN)
        
        new_admin_username = request.data.get('member_username')
        try:
            new_admin = Member.objects.get(username=new_admin_username)
            if OrganizationManager.objects.filter(organization=organization, member=new_admin).exists():
                return Response({"error": "This member is already an admin."}, status=status.HTTP_400_BAD_REQUEST)            
            OrganizationManager.objects.create(
                organization=organization,
                member=new_admin,
                access_level=OrganizationManager.LIMITED_ACCESS,
                is_approved=True
            )
            logger.info(f"User {user.username} added new admin {new_admin.username} with limited access in organization {organization.slug}")
            return Response({"message": "New admin with limited access added successfully"}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            logger.error(f"New admin {new_admin_username} not found for adding to organization {organization.slug}")
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    # Remove Limited Access Admin
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin])
    def remove_admin(self, request, pk=None):
        organization = self.get_object()        
        user = request.user.member
        try:
            manager = OrganizationManager.objects.get(organization=organization, member=user)
            if manager.access_level != OrganizationManager.FULL_ACCESS:
                return Response({"error": "Only admins with full access can remove admins."}, status=status.HTTP_403_FORBIDDEN)
        except OrganizationManager.DoesNotExist:
            return Response({"error": "You are not an admin of this organization."}, status=status.HTTP_403_FORBIDDEN)
        admin_id = request.data.get('member_id')
        try:
            admin = Member.objects.get(id=admin_id)
            admin_manager = OrganizationManager.objects.filter(organization=organization, member=admin).first()
            if not admin_manager:
                return Response({"error": "This member is not an admin in this organization."}, status=status.HTTP_404_NOT_FOUND)
            if admin_manager.access_level != OrganizationManager.LIMITED_ACCESS:
                return Response({"error": "Only admins with limited access can be removed this way."}, status=status.HTTP_400_BAD_REQUEST)
            admin_manager.delete()
            logger.info(f"Admin {admin.username} with limited access removed from organization {organization.slug}")
            return Response({"message": "Admin with limited access removed successfully"}, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            logger.error(f"Admin {admin_id} not found for removal from organization {organization.slug}")
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        except OrganizationManager.DoesNotExist:
            logger.error(f"Admin {admin_id} not found in OrganizationManager for organization {organization.slug}")
            return Response({"error": "This member is not an admin in this organization."}, status=status.HTTP_404_NOT_FOUND)
        

# VOTING STATUS Mixin ---------------------------------------------------------------------------------
class VotingStatusMixin:
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='voting_status')
    def voting_status(self, request, slug=None):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        organization = self.get_object()
        user = request.user.member
        if user.username not in organization.org_owners.values_list('username', flat=True):
            return Response({"error": "Only owners can view the voting status."}, status=status.HTTP_403_FORBIDDEN)
        voting_data = {}
        voting_histories = VotingHistory.objects.filter(organization=organization, result__isnull=True).order_by('-created_at')
        for voting_history in voting_histories:
            vote_info = {
                "voting_type": voting_history.voting_type,
                "description": voting_history.description,
                "total_votes": voting_history.voted_users.count(),
                "votes_required": voting_history.votes_required,
                "voted_users": list(voting_history.voted_users.values_list('username', flat=True)),
                "non_voted_users": list(organization.org_owners.exclude(username__in=voting_history.voted_users.values_list('username', flat=True)).values_list('username', flat=True))
            }
            voting_data[voting_history.voting_type] = vote_info
        return Response(voting_data, status=status.HTTP_200_OK)
