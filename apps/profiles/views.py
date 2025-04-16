from django.db.models import Q, F
from django.db import transaction
from django.utils import timezone
from datetime import timedelta


from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework import serializers

from cryptography.fernet import Fernet
from django.conf import settings
cipher_suite = Fernet(settings.FERNET_KEY)

from .services import (
                    add_symmetric_friendship, remove_symmetric_friendship, 
                    add_symmetric_fellowship, remove_symmetric_fellowship,
                    calculate_spiritual_gifts_scores, calculate_top_3_gifts
                )
from .models import (
                    Member, GuestUser, Friendship, Fellowship, MigrationHistory,
                    SpiritualGiftSurveyResponse, MemberSpiritualGifts,
                    SpiritualGiftSurveyQuestion, MemberSurveyProgress,
                )
from .serializers import (
                    FriendshipSerializer, FellowshipSerializer,
                    MemberSerializer, PublicMemberSerializer, LimitedMemberSerializer,
                    GuestUserSerializer, LimitedGuestUserSerializer,
                    SpiritualGiftSurveyResponseSerializer, SpiritualGiftSurveyQuestionSerializer, MemberSpiritualGiftsSerializer, SpiritualGift
                )
from apps.accounts.serializers import SimpleCustomUserSerializer
from common.validators import validate_phone_number
from django.core.exceptions import ValidationError
from utils import create_veriff_session, get_veriff_status, send_email, create_active_code
from django.template.loader import render_to_string
from services.friendship_suggestions import suggest_friends_for_friends_tab, suggest_friends_for_requests_tab
import logging
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


# PROFILE MIGRATE View ------------------------------------------------------------------------------
class ProfileMigrationViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    # Migrate between GuestUser and Member based on the label
    def migrate_profile(self, request):
        user = request.user
        if user.label == CustomUser.BELIEVER: # For Believers
            if hasattr(user, 'guestuser'):
                guest_profile = user.guestuser
                guest_profile.is_active = False
                guest_profile.is_migrated = True
                guest_profile.save()
                
                user.is_member = True
                user.save()

                member_data = {'name': user.id}
                member_serializer = MemberSerializer(data=member_data)
                if member_serializer.is_valid():
                    member_serializer.save()
                    MigrationHistory.objects.create(
                        user=user,
                        migration_type='guest_to_member'
                    )
                    return Response({"message": "Profile migrated to Member successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response(member_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"message": "User is already a Member."}, status=status.HTTP_400_BAD_REQUEST)

        elif user.label in [CustomUser.SEEKER, CustomUser.PREFER_NOT_TO_SAY]: # For Others
            if hasattr(user, 'member'):
                member_profile = user.member
                member_profile.is_active = False
                member_profile.is_migrated = True
                member_profile.save()

                user.is_member = False
                user.save()

                guest_user_data = {'name': user.id}
                guest_user_serializer = GuestUserSerializer(data=guest_user_data)
                if guest_user_serializer.is_valid():
                    guest_user_serializer.save()
                    MigrationHistory.objects.create(
                        user=user,
                        migration_type='member_to_guest'
                    )
                    return Response({"message": "Profile migrated to GuestUser successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response(guest_user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"message": "User is already a GuestUser."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Invalid label value."}, status=status.HTTP_400_BAD_REQUEST)


# MEMBER PANEL Viewsets -------------------------------------------------------------------------
class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        try:
            member = self.get_object()
            # Check if the member is suspended
            if member.id.is_suspended:
                return Response({"error": "This profile is suspended and cannot be accessed."}, status=status.HTTP_403_FORBIDDEN)
            # Check if the profile is hidden
            if member.is_hidden_by_confidants:
                return Response({"error": "This profile is currently hidden."}, status=status.HTTP_403_FORBIDDEN)
            serializer = self.get_serializer(member, context={'request': request})
            return Response(serializer.data)
        except Member.DoesNotExist:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='my-profile', permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        try:
            print(request.user)
            member = request.user.member
            # Check if the member is suspended
            if member.id.is_suspended:
                return Response({"error": "Your profile is suspended and cannot be accessed by you."}, status=status.HTTP_403_FORBIDDEN)
            if member.is_hidden_by_confidants:
                return Response({"error": "Your profile is currently hidden and cannot be accessed by you."}, status=status.HTTP_403_FORBIDDEN)
            serializer = MemberSerializer(member, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        
    # Update Profile ------------------------------------------------------------------------------------------------    
    @action(detail=False, methods=['post'], url_path='update-profile', permission_classes=[IsAuthenticated])
    def update_profile(self, request):        
        try:
            member = request.user.member
            serializer = MemberSerializer(member, data=request.data, partial=True)
            if serializer.is_valid():
                updated_member = serializer.save()
                return Response({"message": "Profile updated successfully.","data": MemberSerializer(updated_member).data},status=status.HTTP_200_OK)
            raise serializers.ValidationError({"error": "Invalid data. Please check the provided fields.", "details": serializer.errors})

        except Member.DoesNotExist:
            # Return a clear error when no profile is found for the user
            return Response({"error": "Profile not found. Please create a profile first."}, status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as e:
            return Response({"error": "Validation error occurred."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Handle any unexpected exceptions
            return Response({"error": "An unexpected error occurred.",},status=status.HTTP_500_INTERNAL_SERVER_ERROR)    
        
    # Update Profile Image ------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='update-profile-image', permission_classes=[IsAuthenticated])
    def update_profile_image(self, request):
        try:
            profile_image = request.FILES.get('profile_image')
            if not profile_image:
                return Response({"error": "No profile image uploaded"}, status=status.HTTP_400_BAD_REQUEST)
            
            member = request.user.member
            custom_user = member.id
            custom_user.image_name = profile_image
            custom_user.save()
            
            return Response({"message": "Profile image updated successfully.", "data": MemberSerializer(member).data}, status=status.HTTP_200_OK)

        except Member.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # View Member Profile ------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='profile/(?P<username>[^/.]+)', permission_classes=[IsAuthenticated])
    def view_member_profile(self, request, username=None):
        try:
            member = Member.objects.get(id__username=username)

            # بررسی حالت مسدودیت پروفایل
            if member.id.is_suspended:
                return Response({"error": "This profile is suspended."}, status=status.HTTP_403_FORBIDDEN)

            # بررسی حالت مخفی بودن توسط اشخاص مورد اعتماد
            if member.is_hidden_by_confidants:
                confidants = Fellowship.objects.filter(
                    to_user=member.id,
                    fellowship_type="Confidant",
                    status="Accepted"
                ).values_list("from_user", flat=True)

                # اگر کاربر مورد اعتماد است
                if request.user.id in confidants:
                    serializer = PublicMemberSerializer(member, context={'request': request})
                else:
                    serializer = LimitedMemberSerializer(member, context={'request': request})

            # بررسی حالت محدودیت
            elif member.is_privacy:
                if Friendship.objects.filter(from_user=request.user, to_user=member.id).exists():
                    serializer = PublicMemberSerializer(member, context={'request': request})
                else:
                    serializer = LimitedMemberSerializer(member, context={'request': request})

            # حالت عادی
            else:
                serializer = PublicMemberSerializer(member, context={'request': request})

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Member.DoesNotExist:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)



    # Email Actions -------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='request-email-change', permission_classes=[IsAuthenticated])
    def request_email_change(self, request):
        try:
            user = request.user
            new_email = request.data.get('new_email')
            
            # Validate the new email address & 30 Days & not already used
            if not new_email or not isinstance(new_email, str):
                return Response({"error": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)
            if user.last_email_change and timezone.now() - user.last_email_change < timedelta(days=30):
                return Response({"error": "You can only change your email once per month."}, status=status.HTTP_403_FORBIDDEN)
            if CustomUser.objects.filter(email=new_email).exists():
                return Response(
                    {"error": "The new email is already associated with another account."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            old_email_code = create_active_code(5)
            new_email_code = create_active_code(5)
            user.email_change_tokens = {
                "old_email_code": old_email_code,
                "new_email_code": new_email_code,
                "new_email": new_email,
            }
            user.save()

            # Send email to the current email address
            subject_old = "Email Change Request - Confirm with Current Email"
            email_body_old = render_to_string("emails/email_change_old.html", {
                "username": user.username,
                "code": old_email_code,
            })
            send_email(subject_old, '', email_body_old, [user.email])

            # Send email to the new email address
            subject_new = "Verify Your New Email"
            email_body_new = render_to_string("emails/email_change_new.html", {
                "username": user.username,
                "code": new_email_code,
            })
            send_email(subject_new, '', email_body_new, [new_email])

            return Response({"message": "Verification codes have been sent to your current and new email addresses."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "An unexpected error occurred.", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='confirm-email-change', permission_classes=[IsAuthenticated])
    def confirm_email_change(self, request):
        try:
            user = request.user
            old_email_code = request.data.get('old_email_code')
            new_email_code = request.data.get('new_email_code')

            # Check if the email change request exists
            if not user.email_change_tokens:
                return Response({"error": "No email change request found."}, status=status.HTTP_400_BAD_REQUEST)

            # Validate the provided codes
            if not old_email_code or not new_email_code:
                return Response({"error": "Both verification codes are required."}, status=status.HTTP_400_BAD_REQUEST)

            if (
                str(user.email_change_tokens.get("old_email_code")) != str(old_email_code) or
                str(user.email_change_tokens.get("new_email_code")) != str(new_email_code)
            ):
                return Response({"error": "Invalid verification codes."}, status=status.HTTP_400_BAD_REQUEST)
            user.email = user.email_change_tokens.get("new_email")
            user.last_email_change = timezone.now()
            user.email_change_tokens = None
            user.save()

            # Notify the user about the successful email change
            subject = "Your Email Has Been Successfully Changed"
            email_body = render_to_string("emails/email_change_notification.html", {
                "username": user.username,
                "new_email": user.email,
            })
            send_email(subject, '', email_body, [user.email])
            return Response({"message": "Email has been successfully updated."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "An unexpected error occurred.", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Phone Number Actions -------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='request-phone-verification', permission_classes=[IsAuthenticated])
    def request_phone_verification(self, request):
        user = request.user
        new_phone = request.data.get('phone_number')
        if not new_phone:
            return Response({"error": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_phone_number(new_phone)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        if user.mobile_number == new_phone:
            return Response({"error": "This phone number is already associated with your account."}, status=status.HTTP_400_BAD_REQUEST)
        try:            
            verification_code = create_active_code(5)
            encrypted_verification_code = cipher_suite.encrypt(str(verification_code).encode())
            user.mobile_verification_code = encrypted_verification_code.decode()
            user.mobile_verification_expiry = timezone.now() + timedelta(minutes=10)
            user.save()

            # دیباگ
            print('===================')
            print(f"Original Code: {verification_code}")  # Delete after test ------------------------------------------------------------------------------
            print('===================')
            
#             if user.name and user.name.strip():
#                 greeting = f"Good to See You {user.name.capitalize()},"  #  Onward
#             else:
#                 greeting = "Greetings,"
#             sms_response = send_sms(
#                 phone_number=new_phone,
# message = f"""{greeting}
# Your Journey of Connections within TownLIT Lives On!

# Your TownLIT Verification Code:
# 🔐 {verification_code}

# This code is valid for 10 minutes. If this wasn’t you, feel free to ignore this message.

# Stay secure,  
# The TownLIT Team 🌍
# """
#             )
#             if not sms_response["success"]:
#                 raise Exception(sms_response["error"])

            return Response({"message": "Verification code sent to the provided phone number."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['post'], url_path='verify-phone', permission_classes=[IsAuthenticated])
    def verify_phone(self, request):
        user = request.user
        phone = request.data.get('phone_number')
        verification_code = request.data.get('activation_code')
        if not verification_code or not phone:
            return Response({"error": "Verification code and phone number are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if not user.mobile_verification_code:
                return Response({"error": "No verification code found. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)            
            try:
                decrypted_code = cipher_suite.decrypt(user.mobile_verification_code.encode()).decode()
            except Exception as e:
                return Response({"error": "An error occurred while processing the verification code."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if decrypted_code != verification_code:
                return Response({"error": "Invalid verification code."}, status=status.HTTP_400_BAD_REQUEST)

            if user.mobile_verification_expiry and timezone.now() > user.mobile_verification_expiry:
                return Response({"error": "Verification code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            if user.mobile_number == phone:
                return Response({"error": "This phone number is already associated with your account."}, status=status.HTTP_400_BAD_REQUEST)
            user.mobile_number = phone
            user.mobile_verification_code = None
            user.mobile_verification_expiry = None
            user.save()
            return Response({"message": "Phone number added successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=False, methods=['post'], url_path='remove-phone', permission_classes=[IsAuthenticated])
    def remove_phone(self, request):
        user = request.user
        if not user.mobile_number:
            return Response({"error": "No phone number associated with this account."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user.mobile_number = None
            user.save()
            return Response({"message": "Phone number removed successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # Action for Change Visibility by Entrusted -----------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='toggle-visibility', permission_classes=[IsAuthenticated])
    def toggle_visibility(self, request):
        try:
            # Extract memberId from request body
            member_id = request.data.get('memberId')
            if not member_id:
                return Response({"error": "Member ID is required."}, status=status.HTTP_400_BAD_REQUEST)
            member = Member.objects.get(id=member_id)

            # Check if the requesting user is a confidant of the target member
            is_confidant = Fellowship.objects.filter(
                from_user=request.user.id,
                to_user=member_id,
                fellowship_type="Entrusted",
                status="Accepted"
            ).exists()
            
            if is_confidant:
                member.is_hidden_by_confidants = not member.is_hidden_by_confidants
                member.is_privacy = True
                member.save()
                return Response({
                    "message": f"Profile visibility changed to {member.is_hidden_by_confidants}. "
                            f"Restricted status is now {member.is_privacy}."
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "You are not authorized to change the visibility of this profile."}, status=status.HTTP_403_FORBIDDEN)
        except Member.DoesNotExist:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)


# MEMBER IDENTITY VERIFICATION Viewset ------------------------------------------------------------------
class VeriffViewSet(viewsets.ViewSet):
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def create_verification_session(self, request, pk=None):
        member = request.user.member

        # Check if the member is already verified
        if member.is_verified_identity:
            return Response({"message": "Your identity is already verified."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            veriff_response = create_veriff_session(member)
            member.veriff_session_id = veriff_response.get('sessionId')
            member.identity_verification_status = 'submitted'
            member.save()
            logger.info(f"Veriff session created for member {member.name.username}")
            return Response(veriff_response, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating Veriff session for member {member.name.username}: {str(e)}")
            return Response({"error": "Unable to create Veriff session."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def get_verification_status(self, request, pk=None):
        member = request.user.member

        # Check if the session exists
        if not member.veriff_session_id:
            return Response({"error": "No verification session found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            veriff_status = get_veriff_status(member.veriff_session_id)
            member.identity_verification_status = veriff_status.get('status')
            
            # If status is verified, update member profile
            if veriff_status.get('status') == 'approved':
                member.is_verified_identity = True
                member.identity_verified_at = timezone.now()
            member.save()
            logger.info(f"Verification status updated for member {member.name.username}: {veriff_status.get('status')}")
            return Response(veriff_status, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching Veriff status for member {member.name.username}: {str(e)}")
            return Response({"error": "Unable to fetch verification status."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# GUESTUSER PANEL Viewsets ---------------------------------------------------------------------
class GuestUserViewSet(viewsets.ModelViewSet):
    queryset = GuestUser.objects.all()
    serializer_class = GuestUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(name__is_active=True)

    @action(detail=False, methods=['get'], url_path='my-profile', permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        try:
            guest_user = request.user.guestuser
            if guest_user.id.is_suspended:
                return Response({"error": "Your account is suspended. Access denied."}, status=status.HTTP_403_FORBIDDEN)
            serializer = self.get_serializer(guest_user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='update-profile', permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        try:
            guest_user = request.user.guestuser
            if guest_user.id.is_suspended:
                return Response({"error": "Your account is suspended. You cannot update your profile."}, status=status.HTTP_403_FORBIDDEN)
            serializer = self.get_serializer(guest_user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def view_guest_profile(self, request, **kwargs):
        try:
            guest_user = GuestUser.objects.get(id=kwargs.get('pk'))
            if guest_user.id.is_suspended:
                return Response({"error": "This guest account is suspended."}, status=status.HTTP_403_FORBIDDEN)
            else:
                serializer = self.get_serializer(guest_user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='request-delete', permission_classes=[IsAuthenticated])
    def request_delete_profile(self, request):
        try:
            guest_user = request.user.guestuser
            if guest_user.id.is_suspended:
                return Response({"error": "Your account is suspended. You cannot request profile deletion."}, status=status.HTTP_403_FORBIDDEN)
            serializer = GuestUserDeleteRequestSerializer(guest_user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Profile deletion requested. You can return within 1 year."}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='reactivate', permission_classes=[IsAuthenticated])
    def reactivate_profile(self, request):
        try:
            guest_user = request.user.guestuser
            if guest_user.id.is_suspended:
                return Response({"error": "Your account is suspended. Reactivation is not allowed."}, status=status.HTTP_403_FORBIDDEN)
            if guest_user.deletion_requested_at and (timezone.now() - guest_user.deletion_requested_at).days < 365:
                guest_user.is_active = True
                guest_user.deletion_requested_at = None
                guest_user.save()
                return Response({"message": "Your profile has been reactivated."}, status=status.HTTP_200_OK)
            return Response({"error": "You cannot reactivate your profile after 1 year."}, status=status.HTTP_400_BAD_REQUEST)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)


# FRIENDSHIP View --------------------------------------------------------------------------------------------
class FriendshipViewSet(viewsets.ModelViewSet):
    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Friendship.objects.filter(
            Q(to_user=user) | Q(from_user=user)
        ).order_by('-created_at')
            
    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                logger.warning("Missing 'to_user_id' in request data.")
                raise serializers.ValidationError({"to_user_id": "This field is required."})

            to_user = serializer.validated_data['to_user_id']
            if to_user == self.request.user:
                logger.warning(f"User {self.request.user.id} tried to send a friend request to themselves.")
                raise serializers.ValidationError("You cannot send a friend request to yourself.")

            # Check for existing active requests
            existing_request = Friendship.objects.filter(
                from_user=self.request.user,
                to_user=to_user,
                is_active=True
            ).exclude(status='declined')
            if existing_request.exists():
                logger.warning(f"Duplicate friend request from user {self.request.user.id} to {to_user.id}.")
                raise serializers.ValidationError("Friendship request already exists.")

            # Check for a reverse friend request
            reverse_request = Friendship.objects.filter(
                from_user=to_user,
                to_user=self.request.user,
                is_active=True,
                status='pending'
            ).exists()
            if reverse_request:
                logger.warning(f"Reverse friend request exists from user {to_user.id} to {self.request.user.id}.")
                raise serializers.ValidationError(
                    "A friend request from this user is already pending. Please respond to that request instead."
                )

            serializer.save(from_user=self.request.user, to_user=to_user, status='pending')
            logger.info(f"Friend request created: {self.request.user.id} -> {to_user.id}")

        except serializers.ValidationError as e:
            logger.error(f"Validation error while creating friend request: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while creating friend request: {e}")
            raise serializers.ValidationError("An unexpected error occurred.")
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # Response with custom message and data
        return Response({
            "message": "Friend request sent successfully!",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['get'], url_path='search-users', permission_classes=[IsAuthenticated])
    def search_users(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response([], status=status.HTTP_200_OK)

        try:
            users = CustomUser.objects.filter(
                username__icontains=query
            ).exclude(id=request.user.id)[:20]

            friends = Friendship.objects.filter(
                Q(from_user=request.user, status='accepted') | Q(to_user=request.user, status='accepted')
            )
            friend_ids = set(friends.values_list('from_user', flat=True)) | set(friends.values_list('to_user', flat=True))

            serializer = SimpleCustomUserSerializer(
                users,
                many=True,
                context={'request': request, 'friend_ids': friend_ids}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during search_users: {e}")
            return Response({'error': 'Unable to search users'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='sent-requests', permission_classes=[IsAuthenticated])
    def sent_requests(self, request):
        try:
            # Get list of sent friend requests.
            sent_requests = Friendship.objects.filter(from_user=request.user, status='pending')
            serializer = self.get_serializer(sent_requests, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response({'error': 'Unable to fetch sent requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    def received_requests(self, request):
        try:
            # Get list of received friend requests.
            received_requests = Friendship.objects.filter(to_user=request.user, status='pending')
            serializer = self.get_serializer(received_requests, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response({'error': 'Unable to fetch received requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='friends-list', permission_classes=[IsAuthenticated])
    def friends_list(self, request):
        try:
            # Get only one side of the symmetric friendship
            friends = Friendship.objects.filter(
                Q(from_user=request.user) | Q(to_user=request.user),
                status='accepted'
            ).filter(
                Q(from_user__id__lt=F('to_user__id')) 
            )

            # Extract unique friends from the filtered queryset
            friends_data = []
            for friendship in friends:
                if friendship.from_user == request.user:
                    friends_data.append(friendship.to_user)
                else:
                    friends_data.append(friendship.from_user)

            serializer = SimpleCustomUserSerializer(friends_data, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in friends_list: {e}")
            return Response({'error': 'Unable to retrieve friends list'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='friends-suggestions', permission_classes=[IsAuthenticated])
    def friends_suggestions(self, request):
        """Get friend suggestions for the Friends tab."""
        user = request.user
        limit = int(request.query_params.get('limit', 5))
        suggestions = suggest_friends_for_friends_tab(user, limit)
        serializer = SimpleCustomUserSerializer(suggestions, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='requests-suggestions', permission_classes=[IsAuthenticated])
    def requests_suggestions(self, request):
        """Get friend suggestions for the Requests tab."""
        user = request.user
        limit = int(request.query_params.get('limit', 5))
        suggestions = suggest_friends_for_requests_tab(user, limit)
        serializer = SimpleCustomUserSerializer(suggestions, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='accept-friend-request', permission_classes=[IsAuthenticated])
    def accept_friend_request(self, request, pk=None):
        try:
            friendship = self.get_object()
            if friendship.to_user != request.user:
                logger.warning(f"User {request.user.id} tried to accept a friendship not directed to them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            if friendship.status == 'pending':
                friendship.status = 'accepted'
                friendship.save()

                # Add symmetric friendship
                success = add_symmetric_friendship(friendship.from_user, friendship.to_user)
                if not success:
                    logger.error(f"Failed to create symmetric friendship for {friendship.from_user.id} and {friendship.to_user.id}")
                    return Response({'error': 'Failed to create symmetric friendship'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Serialize the new friend data
                friend_data = SimpleCustomUserSerializer(friendship.from_user).data
                return Response({'message': 'Friendship accepted', 'friend': friend_data}, status=status.HTTP_200_OK)
            logger.info(f"Friendship {friendship.id} already processed or invalid status.")
            return Response({'error': 'Invalid request or already processed'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friendship request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Unexpected error in accept_friend_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=['post'], url_path='decline-friend-request', permission_classes=[IsAuthenticated])
    def decline_friend_request(self, request, pk=None):
        try:
            friendship = self.get_object()
            if friendship.to_user != request.user:
                logger.warning(f"User {request.user.id} tried to decline a friendship not directed to them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            if friendship.status == 'pending':
                friendship.status = 'declined'
                friendship.is_active = False
                friendship.save()
                logger.info(f"Friendship {friendship.id} declined by user {request.user.id}.")
                return Response({'message': 'Friendship declined'}, status=status.HTTP_200_OK)

            logger.info(f"Friendship {friendship.id} already processed or invalid status.")
            return Response({'error': 'Invalid request or already processed'}, status=status.HTTP_400_BAD_REQUEST)
        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friendship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in decline_friend_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='cancel-request', permission_classes=[IsAuthenticated])
    def cancel_friend_request(self, request, pk=None):
        try:
            friendship = self.get_object()
            if friendship.from_user != request.user:
                logger.warning(f"User {request.user.id} tried to cancel a friendship not initiated by them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            if friendship.status != 'pending':
                logger.info(f"Friendship {friendship.id} cannot be canceled because it is not pending.")
                return Response({'error': 'Only pending requests can be canceled'}, status=status.HTTP_400_BAD_REQUEST)

            friendship.is_active = False
            friendship.status = 'cancelled'
            friendship.save()
            logger.info(f"Friendship {friendship.id} canceled by user {request.user.id}.")
            return Response({'message': 'Friend request canceled.'}, status=status.HTTP_200_OK)
        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in cancel_friend_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='delete-friendships', permission_classes=[IsAuthenticated])
    def delete_friendship(self, request):
        try:
            initiator = request.user
            counterpart_id = request.data.get('friendshipId')
            if not counterpart_id:
                logger.warning(f"User {initiator.id} tried to delete friendship without providing counterpart ID.")
                return Response({'error': 'Counterpart ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

            friendship = Friendship.objects.filter(from_user=initiator, to_user_id=counterpart_id, status='accepted').first()
            if not friendship:
                logger.warning(f"Friendship not found for initiator {initiator.id} and counterpart {counterpart_id}.")
                return Response({'error': 'Friendship not found.'}, status=status.HTTP_404_NOT_FOUND)

            counterpart = friendship.to_user
            if remove_symmetric_friendship(initiator, counterpart):
                logger.info(f"Friendship successfully deleted by user {initiator.id} with counterpart {counterpart.id}.")
                return Response({'message': 'Friendship successfully deleted'}, status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to delete friendship between {initiator.id} and {counterpart.id}.")
                return Response({'error': 'Failed to delete friendship.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Unexpected error in delete_friendship for user {request.user.id}: {e}")
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# FELLOWSHIP View --------------------------------------------------------------------------------------------
class FellowshipViewSet(viewsets.ModelViewSet):
    queryset = Fellowship.objects.all()
    serializer_class = FellowshipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Fellowship.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).order_by('-created_at')

    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                raise serializers.ValidationError({"error": "The 'to_user_id' field is required."})

            to_user = serializer.validated_data['to_user_id']
            fellowship_type = serializer.validated_data['fellowship_type']
            reciprocal_fellowship_type = serializer.validated_data.get('reciprocal_fellowship_type')

            if to_user == self.request.user:
                raise serializers.ValidationError({"error": "You cannot send a fellowship request to yourself."})

            # Check for existing pending requests
            existing_request = Fellowship.objects.filter(
                from_user=self.request.user,
                to_user=to_user,
                fellowship_type=fellowship_type,
                status='Pending'
            )
            if existing_request.exists():
                raise serializers.ValidationError({"error": "A similar fellowship request already exists."})

            # Save the main fellowship relationship
            serializer.save(from_user=self.request.user, reciprocal_fellowship_type=reciprocal_fellowship_type)
            
        except serializers.ValidationError as e:
            raise e
        except Exception as e:
            raise serializers.ValidationError({"error": "An unexpected error occurred."})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response({
            "message": "Fellowship request created successfully!",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'], url_path='search-friends', permission_classes=[IsAuthenticated])
    def search_friends(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response([], status=status.HTTP_200_OK)

        try:
            # Get only one side of the symmetric friendship
            friends = Friendship.objects.filter(
                Q(from_user=request.user) | Q(to_user=request.user),
                status='accepted'
            ).filter(
                Q(from_user__id__lt=F('to_user__id'))
            )

            # Extract unique friends from the filtered queryset
            friends_data = []
            for friendship in friends:
                if friendship.from_user == request.user:
                    friends_data.append(friendship.to_user)
                else:
                    friends_data.append(friendship.from_user)

            # Filter friends based on the query
            filtered_friends = [friend for friend in friends_data if query.lower() in friend.username.lower()]

            # Serialize the filtered friends
            serializer = SimpleCustomUserSerializer(filtered_friends, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in search_friends: {e}")
            return Response({'error': 'Unable to search friends'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='sent-requests', permission_classes=[IsAuthenticated])
    def sent_requests(self, request):
        try:
            sent_requests = Fellowship.objects.filter(from_user=request.user, status='Pending')
            serializer = self.get_serializer(sent_requests, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response({'error': 'Unable to fetch sent requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    def received_requests(self, request):
        try:
            received_requests = Fellowship.objects.filter(to_user=request.user, status='Pending')
            serializer = self.get_serializer(received_requests, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response({'error': 'Unable to fetch received requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='fellowship-list', permission_classes=[IsAuthenticated])
    def fellowship_list(self, request):
        try:
            user = request.user
            fellowships = Fellowship.objects.filter(
                Q(from_user=user) | Q(to_user=user),
                status='Accepted'
            )

            processed_relationships = set()
            result = []
            for fellowship in fellowships:
                if fellowship.from_user == user:
                    opposite_user = fellowship.to_user
                    relationship_type = fellowship.fellowship_type
                elif fellowship.to_user == user:
                    opposite_user = fellowship.from_user
                    relationship_type = fellowship.reciprocal_fellowship_type
                else:
                    continue

                relationship_key = (opposite_user.id, relationship_type)
                if relationship_key not in processed_relationships:
                    is_hidden_by_confidants = (
                        opposite_user.member.is_hidden_by_confidants
                        if hasattr(opposite_user, 'member') and relationship_type == "Entrusted" else None
                    )

                    result.append({
                        'user': SimpleCustomUserSerializer(opposite_user, context={'request': request}).data,
                        'relationship_type': relationship_type,
                        **({'is_hidden_by_confidants': is_hidden_by_confidants} if is_hidden_by_confidants is not None else {})
                    })
                    processed_relationships.add(relationship_key)

            logger.info(f"Processed fellowship list for user {user.id}: {result}")
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in fellowship_list: {e}")
            return Response({'error': 'Unable to retrieve fellowship list'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='accept-request', permission_classes=[IsAuthenticated])
    def accept_request(self, request, pk=None):
        try:
            fellowship = self.get_object()
            
            if fellowship.to_user != request.user:
                logger.warning(f"User {request.user.id} tried to accept a fellowship not directed to them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            reciprocal_fellowship_type = request.data.get('reciprocalFellowshipType')
            if not reciprocal_fellowship_type:
                logger.warning("Missing reciprocalFellowshipType in request data.")
                return Response({'error': 'Reciprocal fellowship type is required.'}, status=status.HTTP_400_BAD_REQUEST)

            if fellowship.status == 'Pending':
                fellowship.status = 'Accepted'
                fellowship.save()
                logger.info(f"Fellowship {fellowship.id} accepted by user {request.user.id}.")

                # Add reciprocal fellowship
                add_symmetric_fellowship(
                    from_user=fellowship.from_user,
                    to_user=fellowship.to_user,
                    fellowship_type=fellowship.fellowship_type,
                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                )
                return Response({'message': 'Fellowship accepted'}, status=status.HTTP_200_OK)

            logger.info(f"Fellowship {fellowship.id} already processed or invalid status.")
            return Response({'error': 'Invalid request or already processed'}, status=status.HTTP_400_BAD_REQUEST)
        except Fellowship.DoesNotExist:
            logger.error(f"Fellowship with id {pk} not found.")
            return Response({'error': 'Fellowship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in accept_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='decline-request', permission_classes=[IsAuthenticated])
    def decline_request(self, request, pk=None):
        try:
            reciprocal_fellowship_type = request.data.get('reciprocalFellowshipType', None)

            if not reciprocal_fellowship_type:
                logger.warning(f"User {request.user.id} did not provide reciprocalFellowshipType.")
                return Response({'error': 'Reciprocal fellowship type is required.'}, status=status.HTTP_400_BAD_REQUEST)

            fellowship = Fellowship.objects.filter(
                id=pk,
                to_user=request.user,
                reciprocal_fellowship_type=reciprocal_fellowship_type,
                status='Pending'
            ).first()

            if not fellowship:
                logger.warning(f"Fellowship with id {pk} and reciprocal type {reciprocal_fellowship_type} not found.")
                return Response({'error': 'Fellowship not found or already processed.'}, status=status.HTTP_404_NOT_FOUND)

            fellowship.delete()
            logger.info(f"Fellowship {pk} declined and deleted by user {request.user.id}.")
            return Response({'message': 'Fellowship request declined successfully.'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error in decline_request for user {request.user.id}: {e}")
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='cancel-request', permission_classes=[IsAuthenticated])
    def cancel_request(self, request, pk=None):
        try:
            fellowship = self.get_object()
            if fellowship.from_user != request.user:
                logger.warning(f"User {request.user.id} tried to cancel a fellowship not initiated by them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            if fellowship.status != 'Pending':
                logger.info(f"Fellowship {fellowship.id} cannot be canceled because it is not pending.")
                return Response({'error': 'Only pending requests can be canceled'}, status=status.HTTP_400_BAD_REQUEST)

            fellowship.delete()
            logger.info(f"Fellowship {fellowship.id} canceled by user {request.user.id}.")
            return Response({'message': 'Fellowship request canceled.'}, status=status.HTTP_200_OK)
        except Fellowship.DoesNotExist:
            logger.error(f"Fellowship with id {pk} not found.")
            return Response({'error': 'Fellowship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in cancel_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='delete-fellowship', permission_classes=[IsAuthenticated])
    def delete_fellowship(self, request):
        try:
            initiator = request.user
            counterpart_id = request.data.get('fellowshipId')
            relationship_type = request.data.get('relationshipType')  # نوع رابطه

            if not counterpart_id or not relationship_type:
                logger.warning(f"User {initiator.id} tried to delete fellowship without providing complete data.")
                return Response({'error': 'Counterpart ID and relationship type are required.'}, status=status.HTTP_400_BAD_REQUEST)

            counterpart_user = CustomUser.objects.filter(id=counterpart_id).first()
            if not counterpart_user:
                logger.warning(f"Counterpart user with ID {counterpart_id} not found.")
                return Response({'error': 'Counterpart user not found.'}, status=status.HTTP_404_NOT_FOUND)

            success = remove_symmetric_fellowship(initiator, counterpart_user, relationship_type)
            if success:
                logger.info(f"Fellowship successfully deleted by user {initiator.id} with counterpart {counterpart_id} ({relationship_type}).")
                return Response({'message': 'Fellowship deleted successfully.'}, status=status.HTTP_200_OK)

            else:
                logger.error(f"Failed to delete fellowship for user {initiator.id} with counterpart {counterpart_id} ({relationship_type}).")
                return Response({'error': 'Failed to delete fellowship.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Unexpected error in delete_fellowship for user {request.user.id}: {e}")
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# MEMBER'S SPIRITUAL GIFT Viewset  ---------------------------------------------------------------------------------
class MemberSpiritualGiftsViewSet(viewsets.ModelViewSet):
    queryset = MemberSpiritualGifts.objects.all()
    serializer_class = MemberSpiritualGiftsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        member = self.request.user.member
        return MemberSpiritualGifts.objects.filter(member=member)
    
    @action(detail=False, methods=['get'], url_path='spiritual-gifts', permission_classes=[IsAuthenticated])
    def get_spiritual_gifts_for_member(self, request):
        member = request.user.member
        member_spiritual_gifts = MemberSpiritualGifts.objects.filter(member=member).first()
        if member_spiritual_gifts:
            serializer = self.get_serializer(member_spiritual_gifts)
            return Response(serializer.data)
        return Response({'message': "You haven't completed the Spiritual Gifts Discovery program yet. Click the button below to get started!"}, status=404)

    @action(detail=False, methods=['post'], url_path='submit-survey', permission_classes=[IsAuthenticated])
    def submit_survey(self, request):
        member = request.user.member
        last_submission = MemberSpiritualGifts.objects.filter(member=member).first()
        
        if last_submission and last_submission.created_at >= timezone.now() - timedelta(days=30):
            return Response({"error": "You can only participate in this course once every 30 days."}, status=status.HTTP_403_FORBIDDEN)

        survey_responses = SpiritualGiftSurveyResponse.objects.filter(member=member)        
        if not survey_responses.exists():
            return Response({"error": "No survey responses found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                member_spiritual_gifts, created = MemberSpiritualGifts.objects.get_or_create(
                    member=member,
                    defaults={"survey_results": {}},
                )
                if not created:
                    member_spiritual_gifts.created_at = timezone.now()

                scores = calculate_spiritual_gifts_scores(member)
                print(f"Scores: {scores}")
                member_spiritual_gifts.survey_results = scores
                member_spiritual_gifts.save()

                top_3_gifts = calculate_top_3_gifts(scores)
                member_spiritual_gifts.gifts.clear()

                for gift_name in top_3_gifts:
                    if isinstance(gift_name, list):
                        for sub_gift in gift_name:
                            gift = SpiritualGift.objects.get(name=sub_gift)
                            member_spiritual_gifts.gifts.add(gift)
                    else:
                        gift = SpiritualGift.objects.get(name=gift_name)
                        member_spiritual_gifts.gifts.add(gift)

                # Delete all survay response
                survey_responses.delete()
                MemberSurveyProgress.objects.filter(member=member).delete()
                
            return Response({"message": "Survey completed successfully. You can retake it once a month."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# MEMBER'S GIFT QUESTIONS Viewset ------------------------------------------------------------------------------------    
class SpiritualGiftSurveyQuestionViewSet(viewsets.ModelViewSet):
    queryset = SpiritualGiftSurveyQuestion.objects.all()
    serializer_class = SpiritualGiftSurveyQuestionSerializer
    permission_classes = [IsAuthenticated]

    # Get all questions for the member in one request
    @action(detail=False, methods=['get'], url_path='gift-questions', permission_classes=[IsAuthenticated])
    def get_gift_questions(self, request):
        language = request.query_params.get('language', 'en')
        questions = self.get_queryset().filter(language=language)        
        serializer = self.get_serializer(questions, many=True)
        return Response(serializer.data)


# SPIRITUAL GIFT SURVEY Viewset ------------------------------------------------------------------------------------    
class SpiritualGiftSurveyViewSet(viewsets.ModelViewSet):
    queryset = SpiritualGiftSurveyResponse.objects.all()
    serializer_class = SpiritualGiftSurveyResponseSerializer
    permission_classes = [IsAuthenticated]
    
    # Get all responses for the current member
    @action(detail=False, methods=['get'], url_path='get-answers', permission_classes=[IsAuthenticated])
    def get_answers(self, request):
        user = request.user.member
        responses = SpiritualGiftSurveyResponse.objects.filter(member=user)
        
        serializer = self.get_serializer(responses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='submit-answer', permission_classes=[IsAuthenticated])
    def submit_answer(self, request, pk=None):
        member = request.user.member
        question_id = request.data.get('question_id')
        question_number = request.data.get('question_number')
        answer = request.data.get('answer')

        if question_number is None or answer is None:
            return Response({'error': 'Question ID and answer are required.'}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(SpiritualGiftSurveyQuestion, id=question_id, question_number=question_number)        
        existing_response = SpiritualGiftSurveyResponse.objects.filter(member=member, question_number=question_number).first()
        if existing_response:
            existing_response.answer = answer
            existing_response.save()
            message = 'Answer updated successfully.'
        else:
            SpiritualGiftSurveyResponse.objects.create(member=member, question=question, question_number=question_number, answer=answer)
            message = 'Answer submitted successfully.'

        progress, created = MemberSurveyProgress.objects.get_or_create(member=member)
        if question_number not in progress.answered_questions:
            progress.answered_questions.append(question_number)
        
        progress.current_question = max(progress.answered_questions)
        progress.save()

        return Response({'message': message}, status=status.HTTP_200_OK)
        
    @action(detail=False, methods=['get'], url_path='get-progress', permission_classes=[IsAuthenticated])
    def get_survey_progress(self, request):
        user = request.user.member
        progress = MemberSurveyProgress.objects.filter(member=user).first()
        total_questions = SpiritualGiftSurveyQuestion.objects.values('question_number').distinct().count()
        
        if progress:
            if progress.current_question > total_questions:
                progress.current_question = total_questions
                progress.save()

            return Response({
                'current_question': progress.current_question,
                'answered_questions': progress.answered_questions
            })
        else:
            return Response({'error': 'No survey progress found.'}, status=status.HTTP_404_NOT_FOUND)
        
    @action(detail=False, methods=['delete'], url_path='cancel-survey', permission_classes=[IsAuthenticated])
    def cancel_survey(self, request):
        member = request.user.member 
        SpiritualGiftSurveyResponse.objects.filter(member=member).delete()        
        MemberSurveyProgress.objects.filter(member=member).delete()
        return Response(
            {'message': 'Survey responses and progress have been reset successfully.'}, 
            status=status.HTTP_200_OK
        )

