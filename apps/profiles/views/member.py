# apps/profiles/views/member.py

from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from cryptography.fernet import Fernet

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.models.member import Member
from apps.profiles.models.relationships import Fellowship
from apps.profiles.serializers.member import MemberSerializer
from apps.accounts.serializers.user_serializers import CustomUserSerializer
from apps.media_conversion.services.readiness import get_media_ready_state

from validators.user_validators import validate_phone_number
from utils.common.utils import create_active_code, send_sms
from utils.email.email_tools import send_custom_email
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)
cipher_suite = Fernet(settings.FERNET_KEY)



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
        user_data = CustomUserSerializer(
            updated_member.user,
            context={'request': request}
        ).data

        member_data = MemberSerializer(
            updated_member,
            context={'request': request}
        ).data
        return Response({
            "message": "Profile updated successfully.",
            "member": member_data,
            "user": user_data,
            # "user": member_data.get("user"),
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

            # Debugging logs
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