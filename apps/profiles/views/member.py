# apps/profiles/views/member.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2023-01-01.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.validators import validate_email as validate_django_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from cryptography.fernet import Fernet

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.services.email_change_security import (
    EMAIL_CHANGE_MAX_ATTEMPTS,
    email_change_expired,
    new_email_change_state,
    pending_new_email,
    verify_email_change_codes,
)
from apps.profiles.models.member import Member
from apps.profiles.models.relationships import Fellowship
from apps.profiles.serializers.member import (
    MemberSerializer,
    LimitedMemberSerializer,
)
from apps.profiles.services.profile_avatar_content_safety import (
    enforce_profile_avatar_content_safety,
)
from apps.accounts.serializers.user_serializers import CustomUserSerializer
from apps.posts.serializers.testimonies import TestimonyProfileHeaderSerializer
from apps.media_conversion.services.readiness import get_media_ready_state
from utils.api.error_response import build_validation_error_response

from validators.user_validators import validate_phone_number
from utils.common.utils import create_active_code, send_sms
from utils.email.email_tools import send_custom_email
from django.contrib.auth import get_user_model
from apps.profiles.services.profile_content_safety import (
    enforce_member_profile_content_safety,
)

CustomUser = get_user_model()
logger = logging.getLogger(__name__)
cipher_suite = Fernet(settings.FERNET_KEY)



# MEMBER PANEL Viewsets -------------------------------------------------------------------------
class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = MemberSerializer

    # Helper for temporarily limited profile response --------------------------
    def _limited_self_profile_response(self, request, member: Member):
        """
        Return a safe limited owner profile when profile access is restricted.

        Do not expose internal safety/confidant reasons to the client.
        """
        data = LimitedMemberSerializer(
            member,
            context={"request": request},
        ).data

        data["profile_gate"] = {
            "key": "profile_temporarily_unavailable",
            "reason": "temporarily_unavailable",
            "redirect_to": f"/lit/{member.user.username}",
            "owner_message": "Your profile is currently unavailable. Please contact TownLIT Support for more information.",
        }

        return Response(data, status=status.HTTP_200_OK)
    
    # Get current user's member profile ---------------------------------------
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
        # Block deleted accounts from reading "self" profile.
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to access your profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        member = self.get_object()

        if member.user_id != request.user.id:
            raise PermissionDenied("You can only access your own profile here.")

        if member.user.is_suspended:
            return Response(
                {"error": "Your profile is suspended and cannot be accessed by you."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Safety gate:
        # Keep the owner profile limited without exposing internal reasons.
        if member.is_hidden_by_confidants:
            return self._limited_self_profile_response(request, member)

        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Get current user's member profile ---------------------------------------
    @action(detail=False, methods=['get'], url_path='my-profile', permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        # Block deleted accounts here too.
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to access your profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            member = request.user.member_profile
        except (Member.DoesNotExist, AttributeError):
            return Response(
                {"error": "Profile not found. Please complete your profile registration."},
                status=status.HTTP_404_NOT_FOUND
            )

        if member.user.is_suspended:
            return Response(
                {"error": "Your profile is suspended and cannot be accessed by you."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Safety gate:
        # Return limited profile with a neutral reason.
        # Never mention confidants, entrusted users, or safety internals.
        if member.is_hidden_by_confidants:
            return self._limited_self_profile_response(request, member)

        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Update current user's member profile ------------------------------------
    @action(detail=False, methods=['post'], url_path='update-profile', permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        # Block updates for deleted accounts.
        if getattr(
            request.user,
            "is_deleted",
            False,
        ):
            return Response(
                {
                    "error": (
                        "Your account is deactivated. "
                        "Reactivate first to update your profile."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            member = request.user.member_profile

        except (
            Member.DoesNotExist,
            AttributeError,
        ):
            return Response(
                {
                    "error": (
                        "Profile not found. "
                        "Please create a profile first."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if member.is_hidden_by_confidants:
            return Response(
                {
                    "code": "profile_temporarily_unavailable",
                    "detail": (
                        "Your profile is currently unavailable. "
                        "Please contact TownLIT Support for "
                        "more information."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(
            member,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return build_validation_error_response(
                serializer.errors
            )

        enforce_member_profile_content_safety(
            validated_data=serializer.validated_data,
            actor=request.user,
            instance=member,
        )

        try:
            with transaction.atomic():
                updated_member = serializer.save()

        except ValidationError as exc:
            if hasattr(
                exc,
                "message_dict",
            ):
                errors = exc.message_dict
            else:
                errors = {
                    "non_field_errors": (
                        getattr(
                            exc,
                            "messages",
                            None,
                        )
                        or [str(exc)]
                    ),
                }

            return build_validation_error_response({
                "user": errors,
            })

        except IntegrityError as exc:
            error_text = str(
                exc
            )

            if (
                "accounts_user_distinct_profile_languages"
                in error_text
            ):
                return build_validation_error_response({
                    "user": {
                        "secondary_language": [
                            (
                                "Primary and secondary languages "
                                "must be different."
                            )
                        ],
                    },
                })

            logger.exception(
                "Member profile update integrity error | user_id=%s",
                request.user.id,
            )

            return Response(
                {
                    "error": (
                        "The profile could not be updated "
                        "because some values conflict."
                    ),
                    "code": "profile_update_conflict",
                },
                status=status.HTTP_409_CONFLICT,
            )

        user_data = CustomUserSerializer(
            updated_member.user,
            context={
                "request": request,
            },
        ).data

        member_data = MemberSerializer(
            updated_member,
            context={
                "request": request,
            },
        ).data

        return Response(
            {
                "message": "Profile updated successfully.",
                "member": member_data,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

    # Update profile avatar ------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='update-profile-image', permission_classes=[IsAuthenticated])
    def update_profile_image(
        self,
        request,
    ):
        if getattr(
            request.user,
            "is_deleted",
            False,
        ):
            return Response(
                {
                    "error": (
                        "Your account is deactivated. "
                        "Reactivate first to change your profile image."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        profile_image = request.FILES.get(
            "profile_image"
        )

        if not profile_image:
            return Response(
                {
                    "error": "No profile image uploaded",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve profile and permissions before performing any
        # provider-backed Content Safety work.
        try:
            member = request.user.member_profile

        except (
            Member.DoesNotExist,
            AttributeError,
        ):
            return Response(
                {
                    "error": "Profile not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if member.is_hidden_by_confidants:
            return Response(
                {
                    "code": "profile_temporarily_unavailable",
                    "detail": (
                        "Your profile is currently unavailable. "
                        "Please contact TownLIT Support for more information."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        custom_user = member.user

        # Content Safety MUST run before mutating CustomUser.
        #
        # BLOCK / REVIEW / provider-unavailable:
        # - existing avatar remains untouched
        # - avatar_version remains untouched
        # - standard Content Safety exception propagates to the client
        enforce_profile_avatar_content_safety(
            file_obj=profile_image,
            actor=request.user,
        )

        # Persist only after Content Safety allows publication.
        custom_user.image_name = profile_image
        custom_user.avatar_version = (
            custom_user.avatar_version
            or 1
        ) + 1

        custom_user.save(
            update_fields=[
                "image_name",
                "avatar_version",
            ]
        )

        member_data = MemberSerializer(
            member,
            context={
                "request": request,
            },
        ).data

        return Response(
            {
                "message": (
                    "Profile image updated successfully."
                ),
                "member": member_data,
                "user": member_data.get(
                    "user"
                ),
            },
            status=status.HTTP_200_OK,
        )

    # Request Email Actions -------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="request-email-change", permission_classes=[IsAuthenticated])
    def request_email_change(self, request):
        new_email = request.data.get("new_email")
        if not isinstance(new_email, str):
            return Response({"error": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)
        new_email = new_email.strip()
        try:
            validate_django_email(new_email)
        except DjangoValidationError:
            return Response({"error": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = CustomUser.objects.select_for_update().get(pk=request.user.pk)
                if user.last_email_change and timezone.now() - user.last_email_change < timedelta(days=30):
                    return Response({"error": "You can only change your email once per month."}, status=status.HTTP_403_FORBIDDEN)
                if CustomUser.objects.filter(email__iexact=new_email).exists():
                    return Response({"error": "The new email is already associated with another account."}, status=status.HTTP_400_BAD_REQUEST)
                previous = user.email_change_tokens or {}
                if previous.get("v") == 2 and not email_change_expired(previous):
                    created_at = parse_datetime(previous.get("created_at", ""))
                    if created_at and timezone.is_aware(created_at) and (timezone.now() - created_at) < timedelta(seconds=60):
                        return Response({"error": "Please wait before requesting new verification codes."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

                old_code = create_active_code(5)
                new_code = create_active_code(5)
                expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
                expiration_time = timezone.now() + timedelta(minutes=expiration_minutes)
                user.email_change_tokens = new_email_change_state(
                    user_id=user.pk,
                    old_code=old_code,
                    new_code=new_code,
                    new_email=new_email,
                    expires_at=expiration_time,
                )
                user.save(update_fields=["email_change_tokens"])
                current_email = user.email
        except Exception:
            logger.error("Email change request preparation failed user_id=%s", request.user.pk)
            return Response({"error": "Unable to create email change request."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        message_common = {
            "user": user,
            "site_domain": settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "expiration_minutes": expiration_minutes,
            "current_year": timezone.now().year,
        }
        for to, subject, template, code in (
            (current_email, "Email Change Request - Confirm with Current Email", "emails/account/email_change_old.html", old_code),
            (new_email, "Verify Your New Email", "emails/account/email_change_new.html", new_code),
        ):
            try:
                success = send_custom_email(
                    to=to,
                    subject=subject,
                    template_path=template,
                    context={**message_common, "code": code},
                    text_template_path=None,
                )
            except Exception:
                success = False
            if not success:
                logger.error("Email change message delivery failed user_id=%s", user.pk)
                # Invalidate the exact request after a failed delivery, without clearing a newer request.
                with transaction.atomic():
                    locked = CustomUser.objects.select_for_update().get(pk=user.pk)
                    if locked.email_change_tokens == user.email_change_tokens:
                        locked.email_change_tokens = None
                        locked.save(update_fields=["email_change_tokens"])
                return Response({"error": "Verification email delivery failed. Please try again later."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            "message": "Verification codes have been sent to both email addresses.",
            "code_type": "email",
            "old_email": current_email,
            "new_email": new_email,
            "expiry_minutes": expiration_minutes,
            "timestamp": timezone.now(),
            "expires_at": expiration_time,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="confirm-email-change", permission_classes=[IsAuthenticated])
    def confirm_email_change(self, request):
        old_code = request.data.get("old_email_code")
        new_code = request.data.get("new_email_code")
        if not old_code or not new_code:
            return Response({"error": "Both verification codes are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = CustomUser.objects.select_for_update().get(pk=request.user.pk)
                state = user.email_change_tokens
                if not isinstance(state, dict) or not state:
                    return Response({"error": "No email change request found."}, status=status.HTTP_400_BAD_REQUEST)
                if email_change_expired(state, legacy_expires_at=user.user_active_code_expiry):
                    user.email_change_tokens = None
                    user.save(update_fields=["email_change_tokens"])
                    return Response({"error": "Verification codes have expired. Request new codes."}, status=status.HTTP_400_BAD_REQUEST)

                attempts = int(state.get("failed_attempts", 0) or 0)
                if attempts >= EMAIL_CHANGE_MAX_ATTEMPTS:
                    user.email_change_tokens = None
                    user.save(update_fields=["email_change_tokens"])
                    return Response({"error": "Too many attempts. Request new verification codes."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
                if not verify_email_change_codes(state, old_code, new_code, user_id=user.pk):
                    attempts += 1
                    state["failed_attempts"] = attempts
                    user.email_change_tokens = None if attempts >= EMAIL_CHANGE_MAX_ATTEMPTS else state
                    user.save(update_fields=["email_change_tokens"])
                    return Response({"error": "Invalid verification codes."}, status=status.HTTP_400_BAD_REQUEST)

                new_email = pending_new_email(state, user.pk)
                if not new_email or CustomUser.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                    return Response({"error": "Email address is no longer available."}, status=status.HTTP_400_BAD_REQUEST)
                user.email = new_email
                user.last_email_change = timezone.now()
                user.email_change_tokens = None
                # The legacy expiry is not used for new v2 requests.
                if state.get("v") != 2:
                    user.user_active_code_expiry = None
                    user.save(update_fields=["email", "last_email_change", "email_change_tokens", "user_active_code_expiry"])
                else:
                    user.save(update_fields=["email", "last_email_change", "email_change_tokens"])
        except IntegrityError:
            return Response({"error": "This email is already in use by another account."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Confirm email change failed user_id=%s", request.user.pk)
            return Response({"error": "Email confirmation failed. Please contact support."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Success is authoritative even if the post-commit notification fails.
        try:
            sent = send_custom_email(
                to=user.email,
                subject="Your Email Has Been Successfully Changed",
                template_path="emails/account/email_change_notification.html",
                context={
                    "user": user,
                    "new_email": user.email,
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": settings.EMAIL_LOGO_URL,
                    "current_year": timezone.now().year,
                },
                text_template_path=None,
            )
            if not sent:
                logger.warning("Email change notification could not be delivered user_id=%s", user.pk)
        except Exception:
            logger.warning("Email change notification failed user_id=%s", user.pk)
        return Response({"message": "Email has been successfully updated."}, status=status.HTTP_200_OK)

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
            logger.info(
                "PHONE_VERIFICATION_SMS_RESULT user_id=%s success=%s",
                user.id,
                bool(sms_response.get("success")),
            )
            if not sms_response["success"]:
                raise Exception(sms_response["error"])
            return Response({
                "message": f"A verification code was sent to {new_phone}. It is valid for {settings.PHONE_CODE_EXPIRATION_MINUTES} minutes.",
                "code_type": "phone",
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": "An unexpected error occurred. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return Response({"error": "An unexpected error occurred. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
