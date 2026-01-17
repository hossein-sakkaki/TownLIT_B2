from django.db.models import Q, Case, When, Value, IntegerField
from django.db.models.functions import Lower, Substr
from django.utils import timezone
from datetime import timedelta
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction

from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from django.contrib.contenttypes.models import ContentType

from apps.posts.models.moment import Moment
from apps.posts.serializers.moments import MomentSerializer
from apps.core.visibility.query import VisibilityQuery
from apps.core.visibility.constants import VISIBILITY_GLOBAL

from apps.core.security.decorators import require_litshield_access
from cryptography.fernet import Fernet
from django.conf import settings
cipher_suite = Fernet(settings.FERNET_KEY)

from apps.profiles.services.symmetric_friendship import (
                    add_symmetric_friendship, remove_symmetric_friendship, 
                )
from apps.profiles.services.symmetric_fellowship import (
                    add_symmetric_fellowship, remove_symmetric_fellowship,
                )
from apps.profiles.services.gifts_service import (
                    calculate_spiritual_gifts_scores, calculate_top_4_gifts
                )
from apps.profiles.services.service_policies import get_policy
from apps.profiles.constants import CONFIDANT
from .models import (
                    Member, GuestUser, Friendship, Fellowship, MigrationHistory,
                    SpiritualGiftSurveyResponse, MemberSpiritualGifts,
                    SpiritualGiftSurveyQuestion, MemberSurveyProgress,
                    SpiritualService,
                )
from .serializers import (
                    FriendshipSerializer, FellowshipSerializer,
                    MemberSerializer, PublicMemberSerializer, LimitedMemberSerializer,
                    GuestUserSerializer, LimitedGuestUserSerializer,
                    SpiritualGiftSurveyResponseSerializer, SpiritualGiftSurveyQuestionSerializer, MemberSpiritualGiftsSerializer, SpiritualGift,
                    MemberServiceTypeSerializer, SpiritualServiceSerializer, MemberServiceType
                )
from apps.accounts.serializers import SimpleCustomUserSerializer
from apps.profiles.services.listing import build_friends_list
from apps.media_conversion.services.readiness import get_media_ready_state  

from validators.user_validators import validate_phone_number
from django.core.exceptions import ValidationError
from utils.common.utils import create_active_code, send_sms
from utils.email.email_tools import send_custom_email
from django.template.loader import render_to_string
from services.friendship_suggestions import suggest_friends_for_friends_tab, suggest_friends_for_requests_tab
from django.contrib.auth import get_user_model
from apps.core.pagination import ConfigurablePagination


import logging
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
                guest_profile = user.guest_profile
                guest_profile.is_active = False
                guest_profile.is_migrated = True
                guest_profile.save()
                
                user.is_member = True
                user.save()

                member_data = {'user': user}
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
                member_profile = user.member_profile
                member_profile.is_active = False
                member_profile.is_migrated = True
                member_profile.save()

                user.is_member = False
                user.save()

                guest_user_data = {'user': user}
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
    serializer_class = MemberSerializer

    def get_queryset(self):
        # If deleted, return no rows (hard stop at the query level)
        if getattr(self.request.user, "is_deleted", False):
            return Member.objects.none()
        return Member.objects.filter(is_active=True, user=self.request.user)

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed('GET')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def retrieve(self, request, *args, **kwargs):
        # Block deleted accounts from reading "self" profile
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to access your profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        member = self.get_object()
        if member.user_id != request.user.id:
            raise PermissionDenied("You can only access your own profile here.")
        if member.user.is_suspended:
            return Response({"error": "Your profile is suspended and cannot be accessed by you."},
                            status=status.HTTP_403_FORBIDDEN)
        if member.is_hidden_by_confidants:
            return Response({"error": "Your profile is currently hidden and cannot be accessed by you."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='my-profile', permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        # Block deleted accounts here too
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to access your profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            member = request.user.member_profile
        except (Member.DoesNotExist, AttributeError):
            return Response({"error": "Profile not found. Please complete your profile registration."},
                            status=status.HTTP_404_NOT_FOUND)

        if member.user.is_suspended:
            return Response({"error": "Your profile is suspended and cannot be accessed by you."},
                            status=status.HTTP_403_FORBIDDEN)
        if member.is_hidden_by_confidants:
            return Response({"error": "Your profile is currently hidden and cannot be accessed by you."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='update-profile', permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        # Block updates for deleted accounts
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to update your profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            member = request.user.member_profile
        except (Member.DoesNotExist, AttributeError):
            return Response({"error": "Profile not found. Please create a profile first."},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(member, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({"error": "Invalid data. Please check the provided fields.",
                             "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        updated_member = serializer.save()
        payload = MemberSerializer(updated_member, context={'request': request}).data
        return Response({
            "message": "Profile updated successfully.",
            "member": payload,
            "user": payload,  # (تدریجاً deprecate)
        }, status=status.HTTP_200_OK)

    # Update profile image ------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='update-profile-image', permission_classes=[IsAuthenticated])
    def update_profile_image(self, request):

        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to change your profile image."},
                status=status.HTTP_403_FORBIDDEN
            )

        profile_image = request.FILES.get('profile_image')
        if not profile_image:
            return Response({"error": "No profile image uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        # Load Member + CustomUser
        try:
            member = request.user.member_profile
        except (Member.DoesNotExist, AttributeError):
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

        custom_user = member.user

        # --- Save image & bump version ---
        custom_user.image_name = profile_image
        custom_user.avatar_version = (custom_user.avatar_version or 1) + 1
        custom_user.save(update_fields=["image_name", "avatar_version"])

        # --- Return updated serializers ---
        member_data = MemberSerializer(member, context={'request': request}).data

        return Response(
            {
                "message": "Profile image updated successfully.",
                "member": member_data,
                "user": member_data.get("user"),   # nested CustomUser
            },
            status=status.HTTP_200_OK
        )

    # Request Email Actions -------------------------------------------------------------------------------------------------
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
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES                      
            expiration_time = timezone.now() + timedelta(minutes=expiration_minutes)
            
            user.user_active_code_expiry = expiration_time
            user.email_change_tokens = {
                "old_email_code": old_email_code,
                "new_email_code": new_email_code,
                "new_email": new_email,
            }
            user.save()

            # Send email to the current email address
            subject = "Email Change Request - Confirm with Current Email"
            context = {
                "user": user,
                "code": old_email_code,
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "expiration_minutes": expiration_minutes,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path="emails/account/email_change_old.html",
                context=context,
                text_template_path=None
            )

            if not success:
                logger.error(f"❌ Failed to send email change confirmation to current email: {user.email}")
                return Response(
                    {"error": "Failed to send confirmation email to your current address. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Send email to the new email address
            subject = "Verify Your New Email"
            context = {
                "user": user,
                "code": new_email_code,
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "expiration_minutes": expiration_minutes,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=new_email,
                subject=subject,
                template_path="emails/account/email_change_new.html",
                context=context,
                text_template_path=None
            )

            if not success:
                logger.error(f"❌ Failed to send verification email to new address: {new_email}")
                return Response(
                    {"error": "Failed to send verification email to the new address. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response({
                "message": f"Verification codes have been sent to {user.email} and {new_email}. They are valid for {expiration_minutes} minutes.",
                "code_type": "email",
                "old_email": user.email,
                "new_email": new_email,
                "expiry_minutes": expiration_minutes,
                "timestamp": timezone.now(),
                "expires_at": expiration_time,
            }, status=status.HTTP_200_OK)

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
            
            if user.user_active_code_expiry and timezone.now() > user.user_active_code_expiry:
                return Response({"error": "The verification codes have expired. Please request a new email change."}, status=status.HTTP_400_BAD_REQUEST)

            tokens = user.email_change_tokens or {}
            new_email = tokens.get("new_email")

            if not new_email:
                return Response(
                    {"error": "Invalid or expired email change request."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                with transaction.atomic():
                    user.email = new_email
                    user.last_email_change = timezone.now()
                    user.email_change_tokens = None
                    user.user_active_code_expiry = None
                    user.save()

            except IntegrityError:
                return Response(
                    {"error": "This email is already in use by another account."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Notify the user about the successful email change
            subject = "Your Email Has Been Successfully Changed"
            context = {
                "user": user,
                "new_email": user.email,
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path="emails/account/email_change_notification.html",
                context=context,
                text_template_path=None
            )

            if not success:
                return Response({"error": "Failed to send email change notification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({"message": "Email has been successfully updated."}, status=status.HTTP_200_OK)
                    
        except Exception as e:
            logger.exception("Confirm email change failed")
            return Response(
                {"error": "Email confirmation failed. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            user.mobile_verification_expiry = timezone.now() + timedelta(minutes=settings.PHONE_CODE_EXPIRATION_MINUTES)
            user.save()

            # دیباگ
            # print('===================')
            # print(f"Original Code: {verification_code}")  # Delete after test ------------------------------------------------------------------------------
            # print('===================')
            
            if user.name and user.name.strip():
                greeting = f"Good to See You {user.name.capitalize()},"  #  Onward
            else:
                greeting = "Greetings,"
            sms_response = send_sms(
                phone_number=new_phone,
message = f"""{greeting}
Your Journey of Connections within TownLIT Lives On!

Your TownLIT Verification Code:
🔐 {verification_code}

This code is valid for 10 minutes. If this wasn’t you, feel free to ignore this message.

Stay secure,  
The TownLIT Team 🌍
"""
            )
            if not sms_response["success"]:
                raise Exception(sms_response["error"])
            return Response({
                "message": f"A verification code was sent to {new_phone}. It is valid for {settings.PHONE_CODE_EXPIRATION_MINUTES} minutes.",
                "code_type": "phone",
            }, status=status.HTTP_200_OK)
        
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
        
    # My Testimonies Summary -----------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='my-testimonies-summary',permission_classes=[IsAuthenticated])
    def my_testimonies_summary(self, request):
        from apps.posts.models.testimony import Testimony

        member = getattr(request.user, "member_profile", None) or getattr(request.user, "member", None)
        if not member:
            return Response(
                {"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ct = ContentType.objects.get_for_model(Member, for_concrete_model=False)
        base_qs = Testimony.objects.filter(content_type=ct, object_id=member.id, is_active=True)

        def pack_written(t: Testimony):
            # Written is not conversion-dependent
            return {
                "exists": True,
                "type": Testimony.TYPE_WRITTEN,
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "published_at": t.published_at,
                "converting": False,
                "excerpt": (t.content[:140] + "…") if t.content and len(t.content) > 140 else (t.content or ""),
            }

        def pack_media(ttype: str, field_name: str):
            t = base_qs.filter(type=ttype).first()
            if not t:
                return {"exists": False}

            # ✅ require_job=True => missing job = NOT ready (prevents race leaks)
            st = get_media_ready_state(t, field_name, require_job=True)

            if not st.ready:
                # 🚫 Do NOT send testimony payload while converting
                # (no id, slug, title, keys, urls, thumbnail, etc.)
                return {
                    "exists": False,                 # prevents "ready card" UI paths
                    "type": ttype,
                    "converting": True,
                    "ready_status": st.status,
                    "job_id": st.job_id,
                    # ✅ only what conversion panel needs
                    "job_target": {
                        "content_type_model": "posts.testimony",  # must match jobs API
                        "object_id": t.id,                        # testimony id is OK (not playable)
                        "field_name": field_name,
                    },
                }

            # ✅ Ready: now safe to return minimal identifiers
            out = {
                "exists": True,
                "type": ttype,
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "published_at": t.published_at,
                "converting": False,
                "ready_status": st.status,
                "job_id": st.job_id,
            }

            # Keys are only meaningful when ready
            if ttype == Testimony.TYPE_AUDIO:
                out["audio_key"] = getattr(t.audio, "name", None)
            else:
                out["video_key"] = getattr(t.video, "name", None)

            return out

        # pick written once
        written = base_qs.filter(type=Testimony.TYPE_WRITTEN).first()

        return Response(
            {
                "audio": pack_media(Testimony.TYPE_AUDIO, "audio"),
                "video": pack_media(Testimony.TYPE_VIDEO, "video"),
                "written": pack_written(written) if written else {"exists": False},
            },
            status=status.HTTP_200_OK,
        )

    # Action for Delete Academic Record -----------------------------------------------------------------------------------
    @action(detail=False, methods=['delete'], url_path='delete-academic-record', permission_classes=[IsAuthenticated])
    def delete_academic_record(self, request):
        """Allow user to delete their academic record."""
        try:
            member = request.user.member_profile
        except (Member.DoesNotExist, AttributeError):
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not member.academic_record:
            return Response({"message": "No academic record found to delete."}, status=status.HTTP_200_OK)

        member.academic_record.delete()
        member.academic_record = None
        member.save(update_fields=["academic_record"])

        return Response({"message": "Academic record deleted successfully."}, status=status.HTTP_200_OK)

# Visitor Profile ViewSet ---------------------------------------------------------------------------------------
class VisitorProfileViewSet(viewsets.GenericViewSet):
    """
    Public-facing profile with privacy gates.
    """
    permission_classes = [AllowAny]
    pagination_class = ConfigurablePagination
    pagination_page_size = 12

    # --- helpers -------------------------------------------------
    def _get_member(self, username: str):
        try:
            return (
                Member.objects.select_related("user", "academic_record")
                .prefetch_related("service_types", "organization_memberships")
                .filter(
                    user__username=username,
                    is_active=True,
                )
                # NULL-safe filter to avoid excluding legacy rows
                .filter(Q(user__is_deleted=False) | Q(user__is_deleted__isnull=True))
                .get()
            )
        except Member.DoesNotExist:
            raise Http404

    def _is_friend(self, viewer, owner_user) -> bool:
        # True if there's an accepted friendship in either direction
        if not viewer or not viewer.is_authenticated:
            return False
        return Friendship.objects.filter(
            Q(from_user=viewer, to_user=owner_user) | Q(from_user=owner_user, to_user=viewer),
            status="accepted",
            is_active=True,
        ).exists()

    def _is_confidant(self, viewer, member: Member) -> bool:
        """
        True iff the profile owner (member.user) has designated the current viewer
        as a 'Confidant' and that fellowship is accepted.
        - Direction matters: owner -> viewer must be CONFIDANT.
        - Status is checked case-insensitively for robustness.
        """
        if not viewer or not viewer.is_authenticated:
            return False

        owner = member.user
        return Fellowship.objects.filter(
            from_user=owner,
            to_user=viewer,
            fellowship_type=CONFIDANT,
            status__iexact='accepted',
        ).exists()


    # -------------------------------------------------------------
    # Visibility gate (Visitor profile moments)
    # -------------------------------------------------------------
    def _visible_moments_qs(self, request, member):
        base = (
            Moment.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # 1) Visibility gate
        if not request.user or not request.user.is_authenticated:
            base = base.filter(visibility=VISIBILITY_GLOBAL)
        else:
            base = VisibilityQuery.for_viewer(
                viewer=request.user,
                base_queryset=base,
            )

        owner_ct = ContentType.objects.get_for_model(member.__class__)

        qs = base.filter(
            content_type_id=owner_ct.id,
            object_id=member.id,
        )

        # 2) 🔐 HARD DOMAIN RULE (Moment video)
        # Never expose video moments until conversion is DONE
        # - blocks False and NULL (anything not True)
        qs = qs.exclude(
            Q(video__isnull=False) & ~Q(is_converted=True)
        )

        return qs
    

    # Helpers -----------------------------------------------------
    def _with_profile_gate(self, data, user, reason):
        """
        Attach profile_gate to a limited serializer response.
        """
        data["profile_gate"] = {
            "key": "profile_privacy_redirect",
            "reason": reason,  # e.g. private_profile | hidden_by_confidants | account_paused
            "redirect_to": f"/lit/{user.username}",
        }
        return data

    # Profile -----------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r'profile/(?P<username>[^/]+)')
    def profile(self, request, username=None):
        """
        GET /profiles/members/profile/<username>/

        Policy:
        - Deleted         -> 404
        - Suspended       -> Limited (+ gate)
        - Paused          -> Limited (+ gate)
        - Hidden-by-conf. -> Limited (+ gate); confidant sees Public
        - Privacy-on      -> Limited (+ gate); friend sees Public
        - Default         -> Public
        """
        member = self._get_member(username)
        user = member.user
        viewer = request.user if request.user.is_authenticated else None

        # -------------------------------------------------
        # 0) Hard deleted -> 404
        # -------------------------------------------------
        if getattr(user, "is_deleted", False):
            return Response(
                {"error": "Member not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # 1) Suspended -> Limited (+ gate)
        # -------------------------------------------------
        if getattr(user, "is_suspended", False):
            data = LimitedMemberSerializer(
                member, context={"request": request}
            ).data
            return Response(
                self._with_profile_gate(
                    data,
                    user,
                    reason="account_suspended",
                ),
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------
        # 2) Account paused -> Limited (+ gate)
        # -------------------------------------------------
        if getattr(user, "is_account_paused", False):
            data = LimitedMemberSerializer(
                member, context={"request": request}
            ).data
            return Response(
                self._with_profile_gate(
                    data,
                    user,
                    reason="account_paused",
                ),
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------
        # 3) Hidden by confidants
        # -------------------------------------------------
        if getattr(member, "is_hidden_by_confidants", False):
            if self._is_confidant(viewer, member):
                data = PublicMemberSerializer(
                    member, context={"request": request}
                ).data
                return Response(data, status=status.HTTP_200_OK)

            data = LimitedMemberSerializer(
                member, context={"request": request}
            ).data
            return Response(
                self._with_profile_gate(
                    data,
                    user,
                    reason="hidden_by_confidants",
                ),
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------
        # 4) Privacy enabled
        # -------------------------------------------------
        if getattr(member, "is_privacy", False):
            if self._is_friend(viewer, user):
                data = PublicMemberSerializer(
                    member, context={"request": request}
                ).data
                return Response(data, status=status.HTTP_200_OK)

            data = LimitedMemberSerializer(
                member, context={"request": request}
            ).data
            return Response(
                self._with_profile_gate(
                    data,
                    user,
                    reason="private_profile",
                ),
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------
        # 5) Default -> Public
        # -------------------------------------------------
        data = PublicMemberSerializer(
            member, context={"request": request}
        ).data
        return Response(data, status=status.HTTP_200_OK)


    # Moments -----------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r'profile/(?P<username>[^/]+)/moments')
    def moments(self, request, username=None):
        """
        GET /profiles/members/profile/<username>/moments/?page=1

        Policy:
          - AllowAny
          - Visibility-aware
          - Returns only this owner's moments
        """
        member = self._get_member(username)
        qs = self._visible_moments_qs(request, member)

        page = self.paginate_queryset(qs)
        serializer = MomentSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)



# ---------------------------------------------------------------------------------------------------------
class MemberServicesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_context(self):
        return {"request": self.request}

    # Services Catalog ------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='services-catalog', permission_classes=[IsAuthenticated])
    def services_catalog(self, request):
        qs = SpiritualService.objects.filter(is_active=True).order_by('is_sensitive', 'name')
        data = SpiritualServiceSerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='my-services', permission_classes=[IsAuthenticated])
    def my_services(self, request):
        member = request.user.member_profile
        qs = (
            MemberServiceType.objects
            .filter(member_service_types=member, is_active=True)
            .select_related('service')
        )
        data = MemberServiceTypeSerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------
    @action(
        detail=False, methods=['post'], url_path='services',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        permission_classes=[IsAuthenticated]
    )
    @transaction.atomic  # ensure all-or-nothing on errors
    def create_service(self, request):
        """Create a MemberServiceType and attach it to current member."""
        # light start log (helpful for tracing, not noisy)
        logger.info("member.services:create start ct=%s keys=%s",
                    request.content_type, list(request.data.keys()))

        # resolve member
        member = getattr(request.user, "member_profile", None)
        if not member:
            logger.warning("member.services:create no-member-profile user_id=%s", request.user.id)
            return Response({"detail": "Member profile not found for current user."},
                            status=status.HTTP_400_BAD_REQUEST)

        # ensure M2M manager exists
        if not hasattr(member, "service_types"):
            logger.error("member.services:create missing M2M 'service_types' on Member id=%s", member.id)
            return Response({"detail": "Server configuration error."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # validate input
        ser = MemberServiceTypeSerializer(data=request.data, context=self.get_serializer_context())
        if not ser.is_valid():
            logger.info("member.services:create invalid payload errors=%s", ser.errors)
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        # prevent duplicates for this member
        service = ser.validated_data["service"]
        if member.service_types.filter(service=service, is_active=True).exists():
            logger.info("member.services:create duplicate service member_id=%s service_id=%s", member.id, service.id)
            return Response({"detail": "This service is already added to your profile."},
                            status=status.HTTP_400_BAD_REQUEST)

        # create + attach
        try:
            instance = ser.save()  # status set by serializer based on is_sensitive
            member.service_types.add(instance)
        except Exception as e:
            logger.exception("member.services:create persistence failed member_id=%s", member.id)
            return Response({"detail": "Failed to create service item."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        out = MemberServiceTypeSerializer(instance, context=self.get_serializer_context()).data
        logger.info("member.services:create ok member_id=%s mst_id=%s", member.id, instance.id)
        return Response(out, status=status.HTTP_201_CREATED)

    # ---------------------------------------------------------------
    @action(
        detail=False, methods=['patch'], url_path=r'services/(?P<pk>\d+)',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        permission_classes=[IsAuthenticated]
    )
    def update_service(self, request, pk=None):
        member = request.user.member_profile
        try:
            instance = (
                MemberServiceType.objects
                .select_related('service')
                .get(pk=pk, is_active=True)
            )
        except MemberServiceType.DoesNotExist:
            return Response({"detail": "Service item not found."}, status=status.HTTP_404_NOT_FOUND)

        # مالکیت: باید به همین member لینک شده باشد
        if not instance.member_service_types.filter(pk=member.pk).exists():
            return Response({"detail": "You don't have permission to modify this service."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data.pop('service_id', None)

        ser = MemberServiceTypeSerializer(instance, data=data, partial=True, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        ser.save()

        return Response(ser.data, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------
    @action(detail=False, methods=['delete'], url_path=r'services/(?P<pk>\d+)', permission_classes=[IsAuthenticated])
    def delete_service(self, request, pk=None):
        member = request.user.member_profile
        try:
            instance = MemberServiceType.objects.select_related('service').get(pk=pk)
        except MemberServiceType.DoesNotExist:
            return Response({"detail": "Service item not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ownership check: must belong to this member
        if not instance.member_service_types.filter(pk=member.pk).exists():
            return Response({"detail": "You don't have permission to remove this service."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            # 1) remove file from storage (if any) to avoid orphaned objects
            if instance.document:
                instance.document.delete(save=False)

            # 2) Hard delete the record; M2M through rows will be removed automatically
            instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='services-policy', permission_classes=[IsAuthenticated])
    def policy(self, request):
        service_code = request.query_params.get("service", None)
        data = get_policy(service_code)
        return Response(data, status=status.HTTP_200_OK)



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
            guest_user = request.user.guest_profile
            if guest_user.user.is_suspended:
                return Response({"error": "Your account is suspended. Access denied."}, status=status.HTTP_403_FORBIDDEN)
            serializer = self.get_serializer(guest_user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='update-profile', permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        try:
            guest_user = request.user.guest_profile
            if guest_user.user.is_suspended:
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
            if guest_user.user.is_suspended:
                return Response({"error": "This guest account is suspended."}, status=status.HTTP_403_FORBIDDEN)
            else:
                serializer = self.get_serializer(guest_user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except GuestUser.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    # @action(detail=False, methods=['post'], url_path='request-delete', permission_classes=[IsAuthenticated])
    # def request_delete_profile(self, request):
    #     try:
    #         guest_user = request.user.guest_profile
    #         if guest_user.user.is_suspended:
    #             return Response({"error": "Your account is suspended. You cannot request profile deletion."}, status=status.HTTP_403_FORBIDDEN)
    #         serializer = GuestUserDeleteRequestSerializer(guest_user, data=request.data, partial=True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response({"message": "Profile deletion requested. You can return within 1 year."}, status=status.HTTP_200_OK)
    #         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    #     except GuestUser.DoesNotExist:
    #         return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='reactivate', permission_classes=[IsAuthenticated])
    def reactivate_profile(self, request):
        try:
            guest_user = request.user.guest_profile
            if guest_user.user.is_suspended:
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
    pagination_class = ConfigurablePagination
    pagination_page_size = 20

    def get_queryset(self):
        user = self.request.user
        return (
            Friendship.objects
            .filter(Q(to_user=user) | Q(from_user=user))
            # exclude any edge where either endpoint is deleted
            .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            .order_by('-created_at')
        )
            
    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                logger.warning("Missing 'to_user_id' in request data.")
                raise serializers.ValidationError({"to_user_id": "This field is required."})

            to_user = serializer.validated_data['to_user_id']

            if not to_user.is_active or getattr(to_user, "is_deleted", False):
                raise serializers.ValidationError(
                    "You cannot send a friend request to this account."
                )

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
    
    # ------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='search-users', permission_classes=[IsAuthenticated])
    def search_users(self, request):
        """
        Fast user search with:
        - optimized queryset (select_related + only)
        - view-aware pagination (ConfigurablePagination)
        - friend status (friend / sent request / received request)
        - excluding deleted users and self
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        try:
            # ------------------------------------------------------------
            # Optimized user lookup
            # ------------------------------------------------------------
            users = (
                CustomUser.objects
                .select_related("label", "member_profile")
                .only(
                    "id", "username", "name", "family", "email",
                    "label__id", "label__name",
                    "member_profile__id",
                    "image_name",
                )
                .filter(
                    Q(username__icontains=query) |
                    Q(name__icontains=query) |
                    Q(family__icontains=query) |
                    Q(email__icontains=query)
                )
                .exclude(id=request.user.id)
                .filter(is_active=True, is_deleted=False)
                .distinct()
            )

            # ------------------------------------------------------------
            # Friendship + request state lookups
            # ------------------------------------------------------------
            friend_edges = Friendship.objects.filter(
                Q(from_user=request.user, status="accepted") |
                Q(to_user=request.user, status="accepted")
            ).values("from_user", "to_user")

            uid = request.user.id
            friend_ids = {
                e["to_user"] if e["from_user"] == uid else e["from_user"]
                for e in friend_edges
            }

            sent_request_map = {
                r["to_user"]: r["id"]
                for r in Friendship.objects.filter(
                    from_user=request.user,
                    status="pending"
                ).values("to_user", "id")
            }

            received_request_map = {
                r["from_user"]: r["id"]
                for r in Friendship.objects.filter(
                    to_user=request.user,
                    status="pending"
                ).values("from_user", "id")
            }

            # ------------------------------------------------------------
            # Pagination (VIEW-AWARE, CORE-COMPATIBLE)
            # ------------------------------------------------------------
            page = self.paginate_queryset(users)
            serializer = SimpleCustomUserSerializer(
                page,
                many=True,
                context={
                    "request": request,
                    "friend_ids": friend_ids,
                    "sent_request_map": sent_request_map,
                    "received_request_map": received_request_map,
                }
            )

            return self.get_paginated_response(serializer.data)

        except Exception as e:
            logger.exception("🔥 search_users failed")
            return Response(
                {"error": "Unable to search users"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='sent-requests', permission_classes=[IsAuthenticated])
    def sent_requests(self, request):
        try:
            qs = (
                Friendship.objects
                .filter(from_user=request.user, status='pending')
                .filter(to_user__is_active=True, to_user__is_deleted=False)
            )
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response({'error': 'Unable to fetch sent requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    def received_requests(self, request):
        try:
            qs = (
                Friendship.objects
                .filter(to_user=request.user, status='pending')
                .filter(from_user__is_deleted=False)
                .filter(from_user__is_active=True, from_user__is_deleted=False)
            )
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response({'error': 'Unable to fetch received requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='friends-list',
        permission_classes=[IsAuthenticated]
    )
    def friends_list(self, request):
        """
        Return optimized list of friends with:
        - alphabetical ordering groups,
        - full serializer context (friend_ids + friendship_ids),
        - fast avatar URLs (via serializer),
        - correct friendship_id for frontend compatibility.
        """
        try:
            user = request.user

            # --- Load friendship edges (accepted + active) ----------------------------
            edges = (
                Friendship.objects
                .filter(
                    Q(from_user=user) | Q(to_user=user),
                    status='accepted',
                    is_active=True,
                )
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .values('id', 'from_user_id', 'to_user_id')
            )

            # --- Build counterpart IDs and friendship_id map -------------------------
            counterpart_ids = set()
            friendship_ids_map = {}   # { user_id: friendship_row_id }
            uid = user.id

            for edge in edges:
                fid = edge['from_user_id']
                tid = edge['to_user_id']

                # find the "other" user
                counterpart = tid if fid == uid else fid
                counterpart_ids.add(counterpart)

                # map that user to the friendship row ID
                friendship_ids_map[counterpart] = edge['id']

            # friend_ids = just counterpart IDs
            friend_ids = counterpart_ids

            # --- Query users with full select_related used by serializer -------------
            friends_qs = (
                CustomUser.objects
                .filter(id__in=counterpart_ids, is_active=True, is_deleted=False)
                .select_related(
                    "label", 
                    "member_profile" 
                )
            )

            # --- Sorting annotations --------------------------------------------------
            first_char = Substr('username', 1, 1)

            group = Case(
                When(username__startswith='_', then=Value(2)),       # group 2: starts with "_"
                When(username__regex=r'^[A-Za-z]', then=Value(0)),  # group 0: A–Z
                default=Value(1),                                   # group 1: others
                output_field=IntegerField(),
            )

            friends_qs = (
                friends_qs
                .annotate(
                    sort_group=group,
                    username_lower=Lower('username'),
                    first_char_annot=first_char,  # for debugging if needed
                )
                .order_by('sort_group', 'username_lower')
            )

            # --- Optional limit ------------------------------------------------------
            limit = request.query_params.get('limit')
            if limit:
                try:
                    lim = max(0, int(limit))
                    if lim:
                        friends_qs = friends_qs[:lim]
                except ValueError:
                    pass  # ignore invalid input

            # --- Serializer with ALL required context --------------------------------
            ser = SimpleCustomUserSerializer(
                friends_qs,
                many=True,
                context={
                    "request": request,

                    # required for serializer logic
                    "friend_ids": friend_ids,
                    "friendship_ids": friendship_ids_map,

                    # optional (for compatibility with other endpoints)
                    "sent_request_map": {},
                    "received_request_map": {},
                    "fellowship_ids": {},
                }
            )

            return Response(
                {"results": ser.data, "meta": {"count": len(counterpart_ids)}},
                status=status.HTTP_200_OK
            )

        except Exception:
            logger.exception("Error in friends_list")
            return Response(
                {"error": "Unable to retrieve friends list"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='friends-suggestions',
        permission_classes=[IsAuthenticated]
    )
    def friends_suggestions(self, request):
        """Return suggestions for the Friends tab."""
        user = request.user
        limit = int(request.query_params.get('limit', 5))

        # suggestions may be a list -> wrap into queryset when possible
        suggestions = suggest_friends_for_friends_tab(user, limit)

        # If it's a QuerySet → annotate & optimize
        if hasattr(suggestions, "select_related"):
            suggestions = suggestions.select_related(
                "label",
                "member_profile"
            )
        else:
            # If it's a list → leave as-is
            suggestions = list(suggestions)

        serializer = SimpleCustomUserSerializer(
            suggestions,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='requests-suggestions',
        permission_classes=[IsAuthenticated]
    )
    def requests_suggestions(self, request):
        """Return suggestions for the Requests tab."""
        user = request.user
        limit = int(request.query_params.get('limit', 5))

        suggestions = suggest_friends_for_requests_tab(user, limit)

        # Detect queryset vs list
        if hasattr(suggestions, "select_related"):
            suggestions = suggestions.select_related(
                "label",
                "member_profile"
            )
        else:
            suggestions = list(suggestions)

        serializer = SimpleCustomUserSerializer(
            suggestions,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


    
    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=True,
        methods=['post'],
        url_path='accept-friend-request',
        permission_classes=[IsAuthenticated]
    )
    def accept_friend_request(self, request, pk=None):
        try:
            # Preload relationships needed by serializer
            friendship = self.get_queryset().select_related(
                "from_user__label",
                "from_user__member_profile",
                "to_user__label",
                "to_user__member_profile",
            ).get(pk=pk)

            # Only the receiver may accept
            if friendship.to_user != request.user:
                logger.warning(f"User {request.user.id} tried to accept a friendship not directed to them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # Cannot accept request from deleted account
            if getattr(friendship.from_user, "is_deleted", False):
                return Response(
                    {'error': 'This request is no longer valid (sender deactivated).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Cannot accept request from inactive account
            if not friendship.from_user.is_active:
                return Response(
                    {'error': 'This request is no longer valid.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process pending request
            if friendship.status == 'pending':
                friendship.status = 'accepted'
                friendship.save()

                # Make symmetric friendship
                success = add_symmetric_friendship(
                    friendship.from_user,
                    friendship.to_user
                )

                if not success:
                    logger.error(
                        f"Failed to create symmetric friendship for {friendship.from_user.id} and {friendship.to_user.id}"
                    )
                    return Response(
                        {'error': 'Failed to create symmetric friendship'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # Serialize the new friend (optimized)
                friend_data = SimpleCustomUserSerializer(
                    friendship.from_user,
                    context={"request": request}
                ).data

                return Response(
                    {'message': 'Friendship accepted', 'friend': friend_data},
                    status=status.HTTP_200_OK
                )

            # Already processed
            logger.info(f"Friendship {friendship.id} already processed or invalid status.")
            return Response(
                {'error': 'Invalid request or already processed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friendship request not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Unexpected error in accept_friend_request: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        
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

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['post'],
        url_path='delete-friendships',
        permission_classes=[IsAuthenticated]
    )
    def delete_friendship(self, request):
        """
        Delete an accepted friendship (symmetric remove).
        Supports both old 'friendshipId' and new 'friendship_id'.
        """
        try:
            initiator = request.user

            # Support both old and new field names
            friendship_id = (
                request.data.get("friendship_id") or
                request.data.get("friendshipId")
            )

            if not friendship_id:
                logger.warning(f"User {initiator.id} attempted deletion with no friendship_id.")
                return Response(
                    {"error": "friendship_id is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Load the friendship row
            friendship = (
                Friendship.objects
                .select_related(
                    "from_user__label", "from_user__member_profile",
                    "to_user__label",   "to_user__member_profile"
                )
                .filter(
                    id=friendship_id,
                    status="accepted",
                    is_active=True
                )
                .first()
            )

            if not friendship:
                logger.warning(f"Friendship not found for delete: id={friendship_id}")
                return Response(
                    {"error": "Friendship not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Ensure the current user is a participant
            if friendship.from_user_id != initiator.id and friendship.to_user_id != initiator.id:
                logger.warning(f"User {initiator.id} tried to delete friendship not belonging to them.")
                return Response(
                    {"error": "You do not have permission to delete this friendship."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Identify counterpart
            counterpart = (
                friendship.to_user
                if friendship.from_user_id == initiator.id
                else friendship.from_user
            )

            # LITCovenant prevention
            existing_fellowship = Fellowship.objects.filter(
                Q(from_user=initiator, to_user=counterpart) |
                Q(from_user=counterpart, to_user=initiator),
                status="Accepted"
            ).exists()

            if existing_fellowship:
                return Response(
                    {
                        "error": (
                            "You cannot delete this friend while a LITCovenant "
                            "relationship is active. Please remove the LITCovenant first."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Symmetric remove
            success = remove_symmetric_friendship(initiator, counterpart)

            if not success:
                logger.error(f"Symmetric friendship removal failed: {initiator.id} <-> {counterpart.id}")
                return Response(
                    {"error": "Failed to delete friendship."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            logger.info(f"Friendship deleted: {initiator.id} <-> {counterpart.id}")

            return Response(
                {"message": "Friendship successfully deleted."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Unexpected error in delete_friendship: {e}")
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




# FELLOWSHIP View --------------------------------------------------------------------------------------------
class FellowshipViewSet(viewsets.ModelViewSet):
    queryset = Fellowship.objects.all()
    serializer_class = FellowshipSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigurablePagination
    pagination_page_size = 20

    # --- helper: serialize list and drop None items ---
    def _serialize_nonnull(self, qs):
        """
        Serialize a queryset of Fellowships and drop None items
        (produced by child.to_representation when endpoints are deleted).
        """
        ser = self.get_serializer(qs, many=True, context=self.get_serializer_context())
        # DRF already evaluated .data -> list; filter out None
        return [item for item in ser.data if item is not None]

    def get_queryset(self):
        user = self.request.user
        return (
            Fellowship.objects
            .select_related(
                "from_user", "to_user",
                "from_user__label", "from_user__member_profile",
                "to_user__label", "to_user__member_profile",
            )
            .filter(Q(from_user=user) | Q(to_user=user))
            .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            .order_by('-created_at')
        )

    
    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                raise serializers.ValidationError({"error": "The 'to_user_id' field is required."})

            to_user = serializer.validated_data['to_user_id']
            fellowship_type = serializer.validated_data['fellowship_type']
            reciprocal_fellowship_type = serializer.validated_data.get('reciprocal_fellowship_type')

            # hard guards
            if getattr(self.request.user, "is_deleted", False):
                raise serializers.ValidationError({"error": "Your account is deactivated. Reactivate to manage fellowships."})
            if getattr(to_user, "is_deleted", False):
                raise serializers.ValidationError({"error": "You cannot send a fellowship request to a deactivated account."})

            if to_user == self.request.user:
                raise serializers.ValidationError({"error": "You cannot send a fellowship request to yourself."})

            # --- Confidant safety: block hidden Confidant re-requests silently ---
            # If user is in 'hide_confidants' mode and this is a Confidant request,
            # and the target is already an accepted Confidant, return a generic error.
            try:
                member = self.request.user.member_profile
                hide_confidants = getattr(member, "hide_confidants", False)
            except Member.DoesNotExist:
                hide_confidants = False

            if hide_confidants and fellowship_type == "Confidant":
                is_hidden_confidant = Fellowship.objects.filter(
                    from_user=self.request.user,
                    to_user=to_user,
                    fellowship_type="Confidant",
                    status="Accepted",
                ).exists()
                if is_hidden_confidant:
                    # Generic error message to avoid leaking security state
                    raise serializers.ValidationError({
                        "error": "Unable to process this request at the moment."
                    })

            # pending dup check (exclude deleted endpoints)
            existing_request = (
                Fellowship.objects
                .filter(
                    from_user=self.request.user,
                    to_user=to_user,
                    fellowship_type=fellowship_type,
                    status='Pending',
                    from_user__is_deleted=False,
                    to_user__is_deleted=False,
                )
            )
            if existing_request.exists():
                raise serializers.ValidationError({"error": "A similar fellowship request already exists."})

            serializer.save(from_user=self.request.user, reciprocal_fellowship_type=reciprocal_fellowship_type)

        except serializers.ValidationError as e:
            raise e
        except Exception:
            raise serializers.ValidationError({"error": "An unexpected error occurred."})


    @require_litshield_access("covenant")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response({
            "message": "Fellowship request created successfully!",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='search-friends', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def search_friends(self, request):
        """
        Search within accepted friends only, with:
        - optimized queryset
        - view-aware pagination (ConfigurablePagination)
        - confidant safety rules
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        try:
            # ------------------------------------------------------------
            # Collect accepted friendship counterpart IDs (fast + safe)
            # ------------------------------------------------------------
            edges = (
                Friendship.objects
                .filter(
                    Q(from_user=request.user) | Q(to_user=request.user),
                    status="accepted",
                    is_active=True,
                )
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .values("from_user_id", "to_user_id")
            )

            uid = request.user.id
            friend_ids = {
                e["to_user_id"] if e["from_user_id"] == uid else e["from_user_id"]
                for e in edges
            }

            if not friend_ids:
                return Response([], status=status.HTTP_200_OK)

            # ------------------------------------------------------------
            # Base friends queryset
            # ------------------------------------------------------------
            friends = (
                CustomUser.objects
                .select_related("label", "member_profile")
                .filter(id__in=friend_ids, is_deleted=False, is_active=True)
                .filter(
                    Q(username__icontains=query) |
                    Q(email__icontains=query) |
                    Q(name__icontains=query) |
                    Q(family__icontains=query)
                )
                .distinct()
            )

            # ------------------------------------------------------------
            # Confidant safety (hide accepted confidants if enabled)
            # ------------------------------------------------------------
            try:
                member = request.user.member_profile
                hide_confidants = getattr(member, "hide_confidants", False)
            except Member.DoesNotExist:
                hide_confidants = False

            if hide_confidants:
                hidden_confidant_ids = Fellowship.objects.filter(
                    from_user=request.user,
                    fellowship_type="Confidant",
                    status="Accepted",
                ).values_list("to_user_id", flat=True)

                friends = friends.exclude(id__in=hidden_confidant_ids)

            # ------------------------------------------------------------
            # Pagination (VIEW-AWARE, CORE-COMPATIBLE)
            # ------------------------------------------------------------
            page = self.paginate_queryset(friends)
            serializer = SimpleCustomUserSerializer(
                page,
                many=True,
                context={"request": request}
            )

            return self.get_paginated_response(serializer.data)

        except Exception:
            logger.exception("🔥 search_friends failed")
            return Response(
                {"error": "Unable to search friends"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='sent-requests', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def sent_requests(self, request):
        try:
            qs = (
                Fellowship.objects
                .select_related(
                    "from_user", "to_user",
                    "from_user__label", "from_user__member_profile",
                    "to_user__label", "to_user__member_profile",
                )
                .filter(from_user=request.user, status='Pending')
                # defense-in-depth (already handled in serializer, but cheap filter too)
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .order_by('-created_at')
            )
            clean = self._serialize_nonnull(qs)
            return Response(clean, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response({'error': 'Unable to fetch sent requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def received_requests(self, request):
        try:
            qs = (
                Fellowship.objects
                .select_related(
                    "from_user", "to_user",
                    "from_user__label", "from_user__member_profile",
                    "to_user__label", "to_user__member_profile",
                )
                .filter(to_user=request.user, status='Pending')
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .order_by('-created_at')
            )
            clean = self._serialize_nonnull(qs)
            return Response(clean, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response({'error': 'Unable to fetch received requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='fellowship-list', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def fellowship_list(self, request):
        try:
            user = request.user
            fellowships = (
                Fellowship.objects
                .select_related(
                    "from_user", "to_user",
                    "from_user__member_profile", "to_user__member_profile",
                    "from_user__label", "to_user__label",
                )

                .filter(Q(from_user=user) | Q(to_user=user), status='Accepted')
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            )

            processed_relationships = set()
            result = []

            should_hide_confidants = getattr(user.member_profile, "hide_confidants", False)

            for fellowship in fellowships:
                if fellowship.from_user == user:
                    opposite_user = fellowship.to_user
                    relationship_type = fellowship.fellowship_type
                else:
                    opposite_user = fellowship.from_user
                    relationship_type = fellowship.reciprocal_fellowship_type

                # skip deleted counterpart (defense in depth)
                if getattr(opposite_user, "is_deleted", False):
                    continue

                if should_hide_confidants and relationship_type == "Confidant":
                    continue

                if relationship_type == "Confidant":
                    if not getattr(user, "pin_security_enabled", False):
                        continue

                if relationship_type == "Entrusted":
                    try:
                        if not getattr(opposite_user, "pin_security_enabled", False):
                            continue
                    except Exception:
                        continue

                key = (opposite_user.id, relationship_type)
                if key in processed_relationships:
                    continue

                is_hidden_by_confidants = (
                    getattr(getattr(opposite_user, "member_profile", None), "is_hidden_by_confidants", None)
                    if relationship_type == "Entrusted" else None
                )

                user_data = SimpleCustomUserSerializer(
                    opposite_user,
                    context={'request': request, 'fellowship_ids': {opposite_user.id: fellowship.id}}
                ).data

                result.append({
                    'user': user_data,
                    'relationship_type': relationship_type,
                    'is_hidden_by_confidants': is_hidden_by_confidants,
                })
                processed_relationships.add(key)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in fellowship_list: {e}")
            return Response({'error': 'Unable to retrieve fellowship list'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='accept-request', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def accept_request(self, request, pk=None):
        try:
            fellowship = self.get_object()
            if fellowship.to_user != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # block if requester is deleted now
            if getattr(fellowship.from_user, "is_deleted", False):
                return Response({'error': 'This request is no longer valid (requester deactivated).'}, status=status.HTTP_400_BAD_REQUEST)

            reciprocal_fellowship_type = request.data.get('reciprocalFellowshipType')
            if not reciprocal_fellowship_type:
                return Response({'error': 'Reciprocal fellowship type is required.'}, status=status.HTTP_400_BAD_REQUEST)

            if fellowship.status == 'Pending':
                fellowship.status = 'Accepted'
                fellowship.save()

                add_symmetric_fellowship(
                    from_user=fellowship.from_user,
                    to_user=fellowship.to_user,
                    fellowship_type=fellowship.fellowship_type,
                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                )
                return Response({'message': 'Fellowship accepted'}, status=status.HTTP_200_OK)

            return Response({'error': 'Invalid request or already processed'}, status=status.HTTP_400_BAD_REQUEST)

        except Fellowship.DoesNotExist:
            return Response({'error': 'Fellowship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in accept_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='decline-request', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def decline_request(self, request, pk=None):
        """
        Decline a pending request:
        1) set status -> 'Declined' and save (fires post_save signal -> notification)
        2) then delete the row (we don't keep declined rows)
        """
        try:
            reciprocal_fellowship_type = request.data.get('reciprocalFellowshipType')
            if not reciprocal_fellowship_type:
                return Response({'error': 'Reciprocal fellowship type is required.'}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                fellowship = (Fellowship.objects
                            .select_for_update()
                            .filter(id=pk,
                                    to_user=request.user,
                                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                                    status='Pending')
                            .first())
                if not fellowship:
                    return Response({'error': 'Fellowship not found or already processed.'}, status=status.HTTP_404_NOT_FOUND)

                # 1) trigger notification
                fellowship.status = 'Declined'
                fellowship.save(update_fields=['status'])  # ✅ post_save → notif

                # 2) cleanup row (no need to keep declined)
                fellowship.delete()

            logger.info(f"Fellowship {pk} declined+deleted by user {request.user.id}.")
            return Response({'message': 'Fellowship request declined.'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error in decline_request: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='cancel-request', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def cancel_request(self, request, pk=None):
        """
        Cancel my own pending outbound request:
        1) set status -> 'Cancelled' and save (fires post_save signal -> notification)
        2) then delete the row (we don't keep cancelled)
        """
        try:
            with transaction.atomic():
                fellowship = (Fellowship.objects
                            .select_for_update()
                            .get(id=pk))

                if fellowship.from_user != request.user:
                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

                if fellowship.status != 'Pending':
                    return Response({'error': 'Only pending requests can be canceled'}, status=status.HTTP_400_BAD_REQUEST)

                # 1) trigger notification
                fellowship.status = 'Cancelled'
                fellowship.save(update_fields=['status'])  # ✅ post_save → notif

                # 2) cleanup row
                fellowship.delete()

            logger.info(f"Fellowship {pk} cancelled+deleted by user {request.user.id}.")
            return Response({'message': 'Fellowship request canceled.'}, status=status.HTTP_200_OK)

        except Fellowship.DoesNotExist:
            return Response({'error': 'Fellowship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in cancel_request: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='delete-fellowship', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def delete_fellowship(self, request):
        """
        Remove an accepted fellowship bidirectionally (unpair):
        Delegates to a helper that:
        - sets 'Cancelled' + save() on exactly ONE side (fires a single notification burst),
        - then deletes BOTH sides.
        """
        try:
            initiator = request.user
            counterpart_id = request.data.get('fellowshipId')
            relationship_type = request.data.get('relationshipType')

            if not counterpart_id or not relationship_type:
                return Response({'error': 'Counterpart ID and relationship type are required.'},
                                status=status.HTTP_400_BAD_REQUEST)

            counterpart_user = CustomUser.objects.filter(id=counterpart_id).first()
            if not counterpart_user:
                return Response({'error': 'Counterpart user not found.'}, status=status.HTTP_404_NOT_FOUND)

            ok = remove_symmetric_fellowship(initiator, counterpart_user, relationship_type)
            if ok:
                return Response({'message': 'Fellowship deleted successfully.'}, status=status.HTTP_200_OK)
            return Response({'error': 'Failed to delete fellowship.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Unexpected error in delete_fellowship: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# MEMBER'S SPIRITUAL GIFT Viewset  ---------------------------------------------------------------------------------
class MemberSpiritualGiftsViewSet(viewsets.ModelViewSet):
    queryset = MemberSpiritualGifts.objects.all()
    serializer_class = MemberSpiritualGiftsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        member = self.request.user.member_profile
        return MemberSpiritualGifts.objects.filter(member=member) 

    @action(detail=False, methods=['get'], url_path='spiritual-gifts', permission_classes=[IsAuthenticated])
    def get_spiritual_gifts_for_member(self, request):
        member = request.user.member_profile
        msg = "You haven't completed the Spiritual Gifts Discovery program yet. Click the button below to get started!"
        obj = MemberSpiritualGifts.objects.filter(member=member).first()
        if not obj:
            return Response(
                {"gifts": [], "created_at": None, "message": msg},
                status=status.HTTP_200_OK  
            )
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='submit-survey', permission_classes=[IsAuthenticated])
    def submit_survey(self, request):
        member = request.user.member_profile
        last_submission = MemberSpiritualGifts.objects.filter(member=member).first()
        
        if last_submission and last_submission.created_at >= timezone.now() - timedelta(days=90):
            return Response({"error": "You can only participate in this course once every 90 days."}, status=status.HTTP_403_FORBIDDEN)

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
                member_spiritual_gifts.survey_results = scores
                member_spiritual_gifts.save()

                top_4_gifts = calculate_top_4_gifts(scores)  # was: calculate_top_3_gifts
                member_spiritual_gifts.gifts.clear()

                # unchanged unpacking pattern (handles list when boundary tie happens)
                for gift_name in top_4_gifts:
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
                
            return Response({"message": "Survey completed successfully. You can retake it once every 90 days."}, status=status.HTTP_200_OK)

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
        user = request.user.member_profile
        responses = SpiritualGiftSurveyResponse.objects.filter(member=user)
        
        serializer = self.get_serializer(responses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='submit-answer', permission_classes=[IsAuthenticated])
    def submit_answer(self, request, pk=None):
        member = request.user.member_profile
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
        user = request.user.member_profile
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
        member = request.user.member_profile 
        SpiritualGiftSurveyResponse.objects.filter(member=member).delete()        
        MemberSurveyProgress.objects.filter(member=member).delete()
        return Response(
            {'message': 'Survey responses and progress have been reset successfully.'}, 
            status=status.HTTP_200_OK
        )

