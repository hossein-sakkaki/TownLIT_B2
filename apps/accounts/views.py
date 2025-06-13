from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from django.conf import settings
import datetime
import traceback

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.contenttypes.models import ContentType

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from cryptography.fernet import Fernet

from .models import UserDeviceKey


from .serializers import (
    CustomUserSerializer,
    RegisterUserSerializer, LoginSerializer,
    VerifyNewBornSerializer, ForgetPasswordSerializer, ResetPasswordSerializer,
    SocialMediaLinkSerializer, SocialMediaLinkReadOnlySerializer, SocialMediaTypeSerializer,
    UserDeviceKeySerializer
    )
from .constants import BELIEVER, SEEKER, PREFER_NOT_TO_SAY
from .models import CustomLabel, SocialMediaLink, SocialMediaType, InviteCode
from apps.profilesOrg.models import Organization
from apps.profiles.models import Member, GuestUser
from apps.main.models import TermsAndPolicy, UserAgreement
from apps.communication.models import ExternalContact
from utils.common.utils import create_active_code, MAIN_URL
from utils.email.email_tools import send_custom_email
from utils.security.dialogue_cleanup import handle_sensitive_dialogue_cleanup
import utils as utils
import logging
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)



# Generate key for encryption ---------------------------------------------------
cipher_suite = Fernet(settings.FERNET_KEY)

# Error Message Extract Method for Actions Return -------------------------------
def extract_first_error_message(errors):
    if isinstance(errors, dict):
        for val in errors.values():
            if isinstance(val, list) and val:
                return val[0]
            elif isinstance(val, str):
                return val
    return "Invalid registration data."


# AUTH View  --------------------------------------------------------------------
class AuthViewSet(viewsets.ViewSet):
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):  # Register
        try:
            ser_data = RegisterUserSerializer(data=request.data)
            email = ser_data.initial_data.get('email')
            existing_user = CustomUser.objects.filter(email=email).first()
            if existing_user:
                if existing_user.is_active:
                    return Response(
                        {"message": "A user with this email already exists. Please log in or use a different email address."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    # کاربر غیرفعال → آپدیت پسورد و ارسال مجدد کد
                    if ser_data.is_valid():
                        existing_user.set_password(ser_data.validated_data['password'])
                        existing_user.user_active_code = None
                        existing_user.user_active_code_expiry = None
                        existing_user.registration_started_at = timezone.now()
                        existing_user.save()

                        try:
                            terms_policy = TermsAndPolicy.objects.get(policy_type='terms_and_conditions')
                            UserAgreement.objects.get_or_create(
                                user=existing_user,
                                policy=terms_policy,
                                defaults={"is_latest_agreement": True}
                            )
                        except TermsAndPolicy.DoesNotExist:
                            return Response(
                                {"message": "Terms and Conditions policy not found."},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                        active_code = create_active_code(5)
                        expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
                        expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
                        encrypted_active_code = cipher_suite.encrypt(str(active_code).encode())
                        existing_user.user_active_code = encrypted_active_code
                        existing_user.user_active_code_expiry = expiration_time
                        existing_user.save()

                        subject = "Welcome back to TownLIT - Verify Again"
                        context = {
                            'activation_code': active_code,
                            'user': existing_user,
                            'site_domain': settings.SITE_URL,
                            "logo_base_url": settings.EMAIL_LOGO_URL,
                            "expiration_minutes": expiration_minutes,
                            'email': existing_user.email,
                            "current_year": timezone.now().year,
                        }

                        success = send_custom_email(
                            to=existing_user.email,
                            subject=subject,
                            template_path='emails/account/activation_email.html',
                            context=context,
                            text_template_path=None
                        )

                        if not success:
                            return Response(
                                {"message": "Failed to send activation email. Please try again later."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                            )                            

                        request.session['user_session'] = {
                            'active_code': encrypted_active_code.decode(),
                            'user_id': existing_user.id,
                            'forget_password': False
                        }
                        request.session.modified = True
                        request.session.save()

                        return Response({
                            "message": "Existing account updated. Please verify the new code.",
                            "redirect_to_verify": True
                        }, status=status.HTTP_200_OK)
                    else:
                        return Response({"message": extract_first_error_message(ser_data.errors)}, status=status.HTTP_400_BAD_REQUEST)


            # در صورت نبود کاربر → مسیر عادی ثبت‌نام
            if ser_data.is_valid():
                user = CustomUser.objects.create_user(
                    email=ser_data.validated_data['email'],
                )
                user.set_password(ser_data.validated_data['password'])
                user.image_name = settings.DEFAULT_PROFILE_IMAGE
                user.save()

                try:
                    terms_policy = TermsAndPolicy.objects.get(policy_type='terms_and_conditions')
                    UserAgreement.objects.create(
                        user=user,
                        policy=terms_policy,
                        is_latest_agreement=True
                    )
                except TermsAndPolicy.DoesNotExist:
                    return Response(
                        {"message": "Terms and Conditions policy not found."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                active_code = create_active_code(5)
                expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
                expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
                encrypted_active_code = cipher_suite.encrypt(str(active_code).encode())
                user.user_active_code = encrypted_active_code
                user.user_active_code_expiry = expiration_time
                user.save()

                subject = "Welcome to TownLIT - Activate Your Account!"
                context = {
                    'activation_code': active_code,
                    'user': user,
                    'site_domain': settings.SITE_URL,
                    "logo_base_url": settings.EMAIL_LOGO_URL,
                    "expiration_minutes": expiration_minutes,
                    'email': user.email,
                    "current_year": timezone.now().year,
                }

                success = send_custom_email(
                    to=user.email,
                    subject=subject,
                    template_path='emails/account/activation_email.html',
                    context=context,
                    text_template_path=None
                )

                if not success:
                    user.delete()
                    return Response(
                        {"message": "Failed to send activation email. Please try again later."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                request.session['user_session'] = {
                    'active_code': encrypted_active_code.decode(),
                    'user_id': user.id,
                    'forget_password': False
                }
                request.session.modified = True
                request.session.save()

                return Response({
                    "message": "User registered successfully and profile created.",
                    "redirect_to_verify": True
                }, status=status.HTTP_200_OK)
                
            return Response(
                {"message": extract_first_error_message(ser_data.errors)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error("Unexpected error during registration:\n%s", traceback.format_exc())
            return Response(
                {"message": "An unexpected error occurred during registration. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verify(self, request):  # Verify
        ser_data = VerifyNewBornSerializer(data=request.data)
        if ser_data.is_valid():
            user_session = request.session.get('user_session')
            if not user_session:
                return Response(
                    {"error": "Session data not found. Please try registering again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            encrypted_active_code = user_session.get('active_code')
            if not encrypted_active_code:
                return Response(
                    {"error": "No activation code found in session. Please try registering again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                # Decrypt the activation code
                decrypted_active_code = cipher_suite.decrypt(encrypted_active_code.encode()).decode()
            except Exception as e:
                logger.error(f"Decryption error: {str(e)}")
                return Response(
                    {"error": "An error occurred while processing your activation code. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            if decrypted_active_code != ser_data.validated_data['active_code']:
                return Response(
                    {"error": "Incorrect activation code. Please check and try again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                user = CustomUser.objects.get(id=user_session['user_id'])
            except CustomUser.DoesNotExist:
                return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)
            if user.user_active_code_expiry and timezone.now() > user.user_active_code_expiry:
                return Response(
                    {"error": "Activation code has expired. Please register again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.user_active_code = None
            user.user_active_code_expiry = None
            user.is_active = False
            user.save()

            return Response({
                "message": "User verified successfully. Please answer the category questions.",
                "redirect_to_choose_path": True
            }, status=status.HTTP_200_OK)
        return Response(
            {"message": extract_first_error_message(ser_data.errors)},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=['post'], url_path='choose-path', permission_classes=[AllowAny])
    def choose_path(self, request):  # Answer the category questions
        user_session = request.session.get('user_session')
        if not user_session:
            return Response({"error": "Session data not found"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = CustomUser.objects.get(id=user_session['user_id'])
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

        # Get category and validate it
        category = request.data.get('category')
        if not category or category not in [BELIEVER, SEEKER, PREFER_NOT_TO_SAY]:
            return Response({"error": "Invalid category"}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve the appropriate label
        try:
            label = CustomLabel.objects.get(name=category)
        except CustomLabel.DoesNotExist:
            return Response({"error": "Label not found."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Assign the label and member status to the user
        user.label = label
        if category == BELIEVER:
            user.is_member = True
        try:
            user.save()
            external_contact = ExternalContact.objects.filter(email__iexact=user.email).first()
            if external_contact:
                external_contact.became_user = True
                external_contact.became_user_at = timezone.now()
                external_contact.deleted_after_signup = False
                external_contact.save()
            
        except Exception as e:
            return Response({
                "error": "Unable to save user data. Please try again.",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create or retrieve the profile based on the category
        if category == BELIEVER:
            try:
                member_instance, created = Member.objects.get_or_create(user=user)
            except Exception as e:
                return Response({
                    "error": "Unable to create member profile. Please try again later or contact support.",
                    "details": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                guest_user_instance, created = GuestUser.objects.get_or_create(user=user)
            except Exception as e:
                return Response({
                    "error": "Unable to create guest user profile. Please try again later or contact support.",
                    "details": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        user.last_login = timezone.now()        
        user.is_active = True
        user.save()
        
        # Mark invite code as used, only now that everything is successful
        if getattr(settings, 'USE_INVITE_CODE', False):
            try:
                invite = InviteCode.objects.filter(email__iexact=user.email, used_by__isnull=True).first()
                if invite:
                    invite.mark_as_used(user)
            except Exception as e:
                logger.warning(f"Failed to mark invite as used: {str(e)}")

        
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        user_data = CustomUserSerializer(user).data
        
        return Response({
            'refresh': str(refresh),
            'access': str(access),
            'is_member': user.is_member,
            'user': user_data,
            "message": "Profile created successfully based on the provided category. Welcome to TownLIT!",
            "note": "Feel free to complete your profile or start exploring."
        }, status=status.HTTP_200_OK)
        

    # Login ----------------------------------------------------------------------------------    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        ser_data = LoginSerializer(data=request.data)
        
        if ser_data.is_valid():
            try:
                user = CustomUser.objects.get(email=ser_data.validated_data['email'])
            except CustomUser.DoesNotExist:
                return Response({
                    "message": "We couldn't find an account with this email. If you're new, consider joining the family!"
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # بررسی رمز عبور
            if not user.check_password(ser_data.validated_data['password']):
                return Response({
                    "message": "Hmm... that password didn’t match. Please try again — and don’t worry, it happens!"
                }, status=status.HTTP_401_UNAUTHORIZED)
                

            # بررسی وضعیت is_deleted قبل از ادامه پردازش لاگین
            if user.is_deleted:
                refresh = RefreshToken.for_user(user)
                access = refresh.access_token
                user_data = CustomUserSerializer(user).data
                return Response({                    
                    
                    "message": "Your account deletion request is in progress. You can reactivate your account within 1 year.",
                    "is_deleted": True,
                    "deletion_requested_at": user.deletion_requested_at,
                    "email": user.email,
                    "user_id": user.id,
                    "refresh": str(refresh),
                    "access": str(access),
                    'user': user_data,
                }, status=status.HTTP_202_ACCEPTED)
            
            if not user.is_active:
                return Response({
                    "message": "User account is not active. Please verify your email or contact support."
                }, status=status.HTTP_403_FORBIDDEN)

            if user.two_factor_enabled:
                otp_code = user.generate_two_factor_token()
                expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES

                # ارسال ایمیل با کد OTP
                subject = "Two-Factor Authentication - Your OTP Code"
                context = {
                    'otp_code': otp_code,
                    'user': user,
                    'site_domain': settings.SITE_URL,  
                    "logo_base_url": settings.EMAIL_LOGO_URL,
                    "current_year": timezone.now().year,
                    "expiration_minutes": expiration_minutes,
                }

                success = send_custom_email(
                    to=user.email,
                    subject=subject,
                    template_path='emails/account/login_by_2fa_email.html',
                    context=context,
                    text_template_path=None 
                )

                if not success:
                    return Response({"error": "Failed to send OTP email. Please try again later."}, status=500)
                                
                return Response({
                    "message": "Two-factor authentication required. Please check your email for the OTP code.",
                    "two_factor_enabled": user.two_factor_enabled,
                    "email": user.email,
                }, status=status.HTTP_202_ACCEPTED)

            # ورود موفق بدون Two-Factor Authentication
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            user_data = CustomUserSerializer(user).data

            return Response({
                'refresh': str(refresh),
                'access': str(access),
                'is_member': user.is_member,
                'two_factor_enabled': user.two_factor_enabled,
                'user': user_data,
                'user_id': user.id
            }, status=status.HTTP_200_OK)

        return Response(
            {"error": extract_first_error_message(ser_data.errors)},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Login with 2FA ----------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='login-with-2fa', permission_classes=[AllowAny])
    def login_with_2fa(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp_code')

        # اعتبارسنجی اولیه
        if not email or not otp_code:
            return Response({
                "message": "Email and OTP code are required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response({
                "message": "User with this email does not exist."
            }, status=status.HTTP_404_NOT_FOUND)

        if not user.two_factor_enabled:
            return Response({
                "message": "Two-factor authentication is not enabled for this user."
            }, status=status.HTTP_400_BAD_REQUEST)

        token_status = user.validate_two_factor_token(otp_code)

        if token_status == "valid":
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            user_data = CustomUserSerializer(user).data

            return Response({
                'refresh': str(refresh),
                'access': str(access),
                'is_member': user.is_member,
                'user': user_data,
                'user_id': user.id,
            }, status=status.HTTP_200_OK)

        elif token_status == "expired":
            return Response({
                "message": "Your OTP code has expired. Please request a new one."
            }, status=status.HTTP_400_BAD_REQUEST)

        elif token_status == "no_token":
            return Response({
                "message": "No OTP code was generated. Please start the login process again."
            }, status=status.HTTP_400_BAD_REQUEST)

        else: 
            return Response({
                "message": "Invalid OTP code. Please try again."
            }, status=status.HTTP_400_BAD_REQUEST)

    # Logout ---------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):  # Logout
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Force Logout from WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{request.user.id}",
                {
                    "type": "force_logout",
                    "user_id": request.user.id,
                }
            )
            
            return Response({"message": "User has been successfully logged out."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid token or token has already been blacklisted."}, status=status.HTTP_400_BAD_REQUEST)
        
        
    # Forgot Password -------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='forget-password', permission_classes=[AllowAny])
    def forget_password(self, request): # Forget Password
        ser_data = ForgetPasswordSerializer(data=request.data)
        if ser_data.is_valid():
            try:
                user = CustomUser.objects.get(email=ser_data.validated_data['email'])  
                reset_token = cipher_suite.encrypt(user.email.encode()).decode()
                expiration_minutes = settings.RESET_LINK_EXPIRATION_MINUTES
                expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
                user.reset_token = reset_token
                user.reset_token_expiration = expiration_time
                user.save()
                reset_link = f'{MAIN_URL}/reset-password/{reset_token}/'
                
                # Send reset your password link via email
                subject = "Password Reset Link"
                context = {
                    'name': user.name or "User",
                    'reset_link': reset_link,
                    "expiration_minutes": expiration_minutes,
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": settings.EMAIL_LOGO_URL,
                    "current_year": timezone.now().year,
                }
                success = send_custom_email(
                    to=user.email,
                    subject=subject,
                    template_path='emails/account/forget_password_email.html',
                    context=context,
                    text_template_path=None 
                )
                if success:
                    return Response({
                        "message": (
                            "A password reset link has been sent to your email. "
                            "Please check your inbox and click the secure link to continue the process. "
                            "If you don’t see the email, kindly check your spam or promotions folder as well."
                        ),
                        "reset_token": reset_token
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "error": (
                            "We couldn’t send the reset link at this moment. "
                            "Please try again later or contact us if the issue continues. "
                            "We’re here to help you regain access with peace and care."
                        )
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                    
            except CustomUser.DoesNotExist:
                return Response({"message": "The provided email does not exist in our system."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ser_data.errors, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='reset-password/(?P<reset_token>[^/.]+)')
    def reset_password(self, request, reset_token):
        try:
            user = CustomUser.objects.get(reset_token=reset_token)
            if user.reset_token_expiration < timezone.now():
                return Response(
                    {"message": "This password reset link has expired. Please request a new one."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except CustomUser.DoesNotExist:
            return Response(
                {"message": "Invalid or expired reset link. Please try again."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            new_password = serializer.validated_data['new_password']

            if check_password(new_password, user.password):
                return Response(
                    {"message": "The new password must be different from your current password."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(new_password)
            user.reset_token = None
            user.reset_token_expiration = None
            user.last_login = timezone.now()
            user.save()

            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            user_data = CustomUserSerializer(user).data

            return Response({
                "refresh": str(refresh),
                "access": str(access),
                "is_member": user.is_member,
                "user": user_data,
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    # Enable 2FA ----------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='enable-2fa', permission_classes=[IsAuthenticated])
    def enable_2fa(self, request):
        user = request.user
        try:
            if user.two_factor_enabled:
                return Response({"message": "Two-factor authentication is already enabled."}, status=status.HTTP_400_BAD_REQUEST)
            otp_code = user.generate_two_factor_token()
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
            
            # Send Email to User
            subject = "Activate Two-Factor Authentication (2FA)"
            context = {
                'otp_code': otp_code,
                'user': user,
                'site_domain': settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "expiration_minutes": expiration_minutes,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path='emails/account/2fa_enable_email.html',
                context=context,
                text_template_path=None
            )

            if not success:
                return Response({"error": "Failed to send OTP email. Please try again later."}, status=500)            
            return Response({"message": "A verification code has been sent to your email."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Verify 2FA
    @action(detail=False, methods=['post'], url_path='verify-2fa-token', permission_classes=[IsAuthenticated])
    def verify_2fa_token(self, request):
        user = request.user
        try:
            otp_code = request.data.get("otp_code")

            if not otp_code:
                return Response({"error": "Verification code is required."}, status=status.HTTP_400_BAD_REQUEST)

            result = user.validate_two_factor_token(otp_code)
            if result == "valid":
                user.two_factor_enabled = True
                user.two_factor_token = None
                user.two_factor_token_expiry = None
                user.save()

                subject = "Two-Factor Authentication Activated"
                context = {
                    "user": user,
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": settings.EMAIL_LOGO_URL,
                    "current_year": timezone.now().year,
                }
                send_custom_email(
                    to=user.email,
                    subject=subject,
                    template_path='emails/account/2fa_enabled_notification.html',
                    context=context,
                    text_template_path=None
                )

                return Response({"message": "Two-factor authentication enabled successfully."}, status=status.HTTP_200_OK)

            elif result == "expired":
                return Response({"error": "The verification code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            elif result == "invalid":
                return Response({"error": "Invalid verification code."}, status=status.HTTP_400_BAD_REQUEST)

            elif result == "no_token":
                return Response({"error": "No verification code found. Please request 2FA setup again."}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"error": "Unexpected verification result."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in verify_2fa_token: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # Disable 2FA -------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='disable-2fa', permission_classes=[IsAuthenticated])
    def disable_2fa(self, request):
        user = request.user
        try:
            if not user.two_factor_enabled:
                return Response({"error": "Two-factor authentication is not enabled."}, status=status.HTTP_400_BAD_REQUEST)
            otp_code = user.generate_two_factor_token()
            
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES

            # Send Email to User
            subject = "Disable Two-Factor Authentication (2FA)"
            context = {
                'otp_code': otp_code,
                'user': user,
                'site_domain': settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "expiration_minutes": expiration_minutes,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path='emails/account/2fa_disable_email.html',
                context=context,
                text_template_path=None
            )

            if not success:
                return Response({"error": "Failed to send OTP email. Please try again later."}, status=500)
                        
            return Response({"message": "A verification code has been sent to your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Verify Disable 2FA
    @action(detail=False, methods=['post'], url_path='verify-disable-2fa-token', permission_classes=[IsAuthenticated])
    def verify_disable_2fa_token(self, request):
        user = request.user
        try:
            otp_code = request.data.get("otp_code")

            if not otp_code:
                return Response({"error": "Verification code is required."}, status=status.HTTP_400_BAD_REQUEST)

            result = user.validate_two_factor_token(otp_code)

            if result == "valid":
                user.two_factor_enabled = False
                user.two_factor_token = None
                user.two_factor_token_expiry = None
                user.save()

                # حذف دستگاه TOTP (اگر استفاده می‌شود)
                TOTPDevice.objects.filter(user=user).delete()

                # ✅ ارسال ایمیل تایید غیرفعال‌سازی 2FA
                subject = "Two-Factor Authentication Disabled"
                context = {
                    "user": user,
                    "site_domain": settings.SITE_URL,
                    "logo_base_url": settings.EMAIL_LOGO_URL,
                    "current_year": timezone.now().year,
                }

                send_custom_email(
                    to=user.email,
                    subject=subject,
                    template_path='emails/account/2fa_disabled_notification.html',
                    context=context,
                    text_template_path=None
                )

                return Response({"message": "Two-factor authentication disabled successfully."}, status=status.HTTP_200_OK)

            elif result == "expired":
                return Response({"error": "The verification code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            elif result == "invalid":
                return Response({"error": "Invalid verification code."}, status=status.HTTP_400_BAD_REQUEST)

            elif result == "no_token":
                return Response({"error": "No verification code found. Please request the disable 2FA process again."}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"error": "Unexpected verification result."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error in verify_disable_2fa_token: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # Change Password In Account -----------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='change-password', permission_classes=[IsAuthenticated])
    def change_password(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response({"error": "Both old and new passwords are required."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(old_password):
            return Response({"error": "The current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "An unexpected error occurred. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # PINs Manage -----------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='enable-pin', permission_classes=[IsAuthenticated])
    def enable_pin(self, request):
        try:
            user = request.user
            if not user.is_member:
                return Response({"error": "Only members can set access and delete pins."}, status=status.HTTP_403_FORBIDDEN)

            access_pin = request.data.get('access_pin')
            delete_pin = request.data.get('delete_pin')
            
            if access_pin and (len(access_pin) != 4 or not access_pin.isdigit()):
                return Response({"error": "Access pin must be 4 numeric digits."}, status=status.HTTP_400_BAD_REQUEST)
            if delete_pin and (len(delete_pin) != 4 or not delete_pin.isdigit()):
                return Response({"error": "Delete pin must be 4 numeric digits."}, status=status.HTTP_400_BAD_REQUEST)
            if access_pin == delete_pin:
                return Response({"error": "Access pin and delete pin must be different."}, status=status.HTTP_400_BAD_REQUEST)

            if access_pin:
                user.set_access_pin(access_pin)
            if delete_pin:
                user.set_delete_pin(delete_pin)
                
            user.pin_security_enabled = True
            user.save()
            return Response({"message": "Pin security enabled and pins set successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['post'], url_path='disable-pin', permission_classes=[IsAuthenticated])
    def disable_pin(self, request):
        try:
            user = request.user
            entered_pin = request.data.get('pin')            
            if not entered_pin:
                return Response({"error": "Pin is required to disable pin security."}, status=status.HTTP_400_BAD_REQUEST)

            if user.verify_access_pin(entered_pin):
                user.access_pin = None
                user.delete_pin = None
                user.pin_security_enabled = False
                user.save()
                return Response({"message": "Security pins removed and pin security disabled."}, status=status.HTTP_200_OK)

            elif user.verify_delete_pin(entered_pin):
                handle_sensitive_dialogue_cleanup(user)
                user.access_pin = None
                user.delete_pin = None
                user.pin_security_enabled = False
                user.save()
                return Response({"message": "Security pins removed, pin security disabled, and all messages deleted."}, status=status.HTTP_200_OK)
            return Response({"error": "Invalid pin entered."}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    @action(detail=False, methods=['post'], url_path='send-delete-confirmation', permission_classes=[IsAuthenticated])
    def send_delete_confirmation(self, request):
        try:
            user = request.user
            if user.is_deleted:
                return Response({"error": "Your account is already marked for deletion."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate and encrypt activation code
            active_code = create_active_code(5)            
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES                      
            expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
            
            encrypted_active_code = cipher_suite.encrypt(str(active_code).encode())
            user.user_active_code = encrypted_active_code.decode()  # Save as string
            user.user_active_code_expiry = expiration_time
            user.save()

            # Send email
            subject = "Confirm Account Deletion - TownLIT"
            context = {
                'activation_code': active_code,
                'user': user,
                'site_domain': settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "expiration_minutes": expiration_minutes,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path='emails/account/delete_confirmation_email.html',
                context=context,
                text_template_path=None
            )

            if not success:
                return Response({"error": "Failed to send confirmation email. Please try again later."}, status=500)

            return Response({"message": "A confirmation email has been sent. Please check your inbox."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in send_delete_confirmation: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['post'], url_path='confirm-delete-account', permission_classes=[AllowAny])
    def confirm_delete_account(self, request):
        try:
            user = request.user
            code = request.data.get('code')

            if not code:
                return Response({"error": "Confirmation code is required."}, status=status.HTTP_400_BAD_REQUEST)

            if not user.user_active_code:
                return Response({"error": "No confirmation code found. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # Decrypt the stored code
            try:
                decrypted_active_code = cipher_suite.decrypt(user.user_active_code.encode()).decode()
            except Exception:
                return Response({"error": "Failed to decrypt the confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the code matches
            if decrypted_active_code != code:
                return Response({"error": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the code has expired
            if user.user_active_code_expiry and timezone.now() > user.user_active_code_expiry:
                return Response({"error": "The confirmation code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # Mark account as deleted
            user.is_deleted = True
            user.deletion_requested_at = timezone.now()
            user.user_active_code = None  # Clear the active code
            user.user_active_code_expiry = None
            user.save()
            
            external_contact = ExternalContact.objects.filter(email__iexact=user.email).first()
            if external_contact:
                external_contact.deleted_after_signup = True
                external_contact.deleted_after_signup_at = timezone.now()
                external_contact.became_user = False
                external_contact.save()

            subject = "Your Account Has Been Deactivated – TownLIT"
            context = {
                "user": user,
                "email": user.email,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "site_domain": settings.SITE_URL,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path='emails/account/account_deleted_confirmation_email.html',
                context=context,
                text_template_path=None
            )

            if not success:
                logger.warning(f"Account deleted but confirmation email failed to send for user {user.email}")
            return Response({
                "message": "Account deletion confirmed. A confirmation email has been sent. You can reactivate your account within 1 year."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in confirm_delete_account: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
            
    @action(detail=False, methods=['post'], url_path='send-reactivate-confirmation', permission_classes=[AllowAny])
    def send_reactivate_confirmation(self, request):
        try:
            user = request.user
            if not user.is_deleted:
                return Response({"error": "Your account is not marked for deletion."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate and encrypt activation code
            active_code = create_active_code(5) 
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES                      
            expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
            
            encrypted_active_code = cipher_suite.encrypt(str(active_code).encode())
            user.user_active_code = encrypted_active_code.decode()  # Save as string
            user.user_active_code_expiry = expiration_time
            user.save()

            # Send email
            subject = "Reactivate Your Account - TownLIT"
            context = {
                'activation_code': active_code,
                'user': user,
                'site_domain': settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "expiration_minutes": expiration_minutes,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path='emails/account/reactivate_account_email.html',
                context=context,
                text_template_path=None  # اگر متن ساده هم بخواهی، می‌توان اضافه کرد
            )

            if not success:
                return Response({"error": "Failed to send reactivation code. Please try again later."}, status=500)

            return Response({"message": "A reactivation code has been sent to your email. Please check your inbox."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in send_reactivate_confirmation: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                
            
    @action(detail=False, methods=['post'], url_path='confirm-reactivate-account', permission_classes=[IsAuthenticated])
    def confirm_reactivate_account(self, request):
        try:
            user = request.user
            code = request.data.get('code')
            
            if not code:
                return Response({"error": "Reactivation code is required."}, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_deleted:
                return Response({"error": "Your account is not marked for deletion."}, status=status.HTTP_400_BAD_REQUEST)

            if not user.user_active_code:
                return Response({"error": "No reactivation code found. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # Decrypt the stored code
            try:
                decrypted_active_code = cipher_suite.decrypt(user.user_active_code.encode()).decode()
            except Exception:
                return Response({"error": "Failed to decrypt the reactivation code."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the code matches
            if decrypted_active_code != code:
                return Response({"error": "Invalid reactivation code."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the code has expired
            if user.user_active_code_expiry and timezone.now() > user.user_active_code_expiry:
                return Response({"error": "The reactivation code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # Reactivate the account
            user.is_deleted = False
            user.deletion_requested_at = None
            user.user_active_code = None  # Clear the active code
            user.user_active_code_expiry = None
            user.reactivated_at = timezone.now()
            user.save()
            external_contact = ExternalContact.objects.filter(email__iexact=user.email).first()
            if external_contact:
                external_contact.became_user = True
                external_contact.became_user_at = timezone.now()
                external_contact.deleted_after_signup = False
                external_contact.save()
                        
            subject = "Welcome Back to TownLIT!"
            context = {
                "user": user,
                "reactivated_at": user.reactivated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "site_domain": settings.SITE_URL,
                "logo_base_url": settings.EMAIL_LOGO_URL,
                "current_year": timezone.now().year,
            }

            success = send_custom_email(
                to=user.email,
                subject=subject,
                template_path="emails/account/reactivation_success_email.html",
                context=context,
                text_template_path=None
            )

            if not success:
                return Response(
                    {"error": "Failed to send reactivation email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )      

            return Response({"message": "Your account has been successfully reactivated."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in confirm_reactivate_account: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # Register Device Key ----------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="register-device-key", permission_classes=[IsAuthenticated])
    def register_device_key(self, request):
        user = request.user
        device_id = request.data.get("device_id")
        public_key = request.data.get("public_key")
        device_name = request.data.get("device_name")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        ip_address = request.META.get("REMOTE_ADDR")

        if not device_id or not public_key:
            return Response({"error": "Device ID and public key are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        device, created = UserDeviceKey.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={
                "public_key": public_key,
                "device_name": device_name,
                "user_agent": user_agent,
                "ip_address": ip_address,
                "last_used": timezone.now(),
                "is_active": True,
            }
        )
        return Response({"message": "Device key registered successfully."})

    @action(detail=False, methods=["get"], url_path="my-devices", permission_classes=[IsAuthenticated])
    def my_devices(self, request):
        user = request.user
        devices = UserDeviceKey.objects.filter(user=user).order_by('-last_used')
        serializer = UserDeviceKeySerializer(devices, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=["delete"], url_path="remove-device/(?P<device_id>[^/.]+)", permission_classes=[IsAuthenticated])
    def remove_device(self, request, device_id=None):
        user = request.user
        try:
            device = UserDeviceKey.objects.get(user=user, device_id=device_id)
            device.delete()
            return Response({"message": f"Device {device_id} removed successfully."})
        except UserDeviceKey.DoesNotExist:
            return Response({"error": "Device not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"], url_path="logout-all-devices")
    def logout_all_devices(self, request):
        user = request.user
        current_device_id = request.data.get("device_id")
        if not current_device_id:
            return Response({"error": "Current device ID is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        # غیرفعال کردن تمام دستگاه‌ها به جز دستگاه فعلی
        UserDeviceKey.objects.filter(user=user).exclude(device_id=current_device_id).update(is_active=False)
        return Response({"message": "All other devices have been logged out."})










# Social Media Links ViewSet ------------------------------------------------------------------------------------
class SocialLinksViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
        
    @action(detail=False, methods=['get'], url_path='list', permission_classes=[IsAuthenticated])
    def list_links(self, request):
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
                
        if not content_type or not object_id:
            return Response({"error": "content_type and object_id are required."}, status=400)

        try:
            links = SocialMediaLink.objects.filter(content_type__model=content_type, object_id=object_id)
            
            if content_type == "customuser" and int(object_id) != request.user.id:
                return Response({"error": "Access denied to this user's links."}, status=403)
            elif content_type == "organization":
                organization = Organization.objects.filter(id=object_id, org_owners=request.user).first()
                if not organization:
                    return Response({"error": "Access denied to this organization's links."}, status=403)

            serializer = SocialMediaLinkReadOnlySerializer(links, many=True, context={'request': request})
            return Response({"links": serializer.data, "message": "Links fetched successfully."}, status=200)

        except (ValueError, TypeError):
            return Response({"error": "Invalid object ID or content_type."}, status=400)


    @action(detail=False, methods=['post'], url_path='add', permission_classes=[IsAuthenticated])
    def add_link(self, request):
        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        social_media_type = request.data.get('social_media_type')
        link = request.data.get('link')

        if not all([content_type, object_id, social_media_type, link]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if content_type == "customuser":
                if int(object_id) != request.user.id:
                    return Response({"error": "You cannot add links to this user."}, status=status.HTTP_403_FORBIDDEN)
                content_object = request.user
            elif content_type == "organization":
                organization = Organization.objects.filter(id=object_id, org_owners=request.user).first()
                if not organization:
                    return Response({"error": "You cannot add links to this organization."}, status=status.HTTP_403_FORBIDDEN)
                content_object = organization
            else:
                return Response({"error": "Invalid content_type provided."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = SocialMediaLinkSerializer(
                data={
                    'social_media_type': social_media_type,
                    'link': link,
                    'content_type': content_type,
                    'object_id': object_id,
                },
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(content_object=content_object)
            return Response({"data": serializer.data, "message": "Social media link added successfully."}, status=status.HTTP_201_CREATED)

        except (ValueError, TypeError):
            return Response({"error": "Invalid object ID or content_type."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'], url_path='delete', permission_classes=[IsAuthenticated])
    def delete_link(self, request):
        link_id = request.query_params.get('id')
        
        if not link_id:
            return Response({"error": "Link ID is required for deletion."}, status=400)

        try:
            link_id = int(link_id)
        except ValueError:
            return Response({"error": "Invalid Link ID."}, status=400)

        try:
            link = SocialMediaLink.objects.get(id=link_id)
            if isinstance(link.content_object, Organization):
                organization = Organization.objects.filter(id=link.content_object.id, org_owners=request.user).first()
                if not organization:
                    return Response({"error": "You cannot delete this link."}, status=403)
            elif link.content_object != request.user:
                return Response({"error": "You cannot delete this link."}, status=403)
            link.delete()
            return Response({"success": True, "message": "Link deleted successfully."}, status=200)

        except SocialMediaLink.DoesNotExist:
            return Response({"error": "Link not found."}, status=404)

    @action(detail=False, methods=['get'], url_path='social-media-types', permission_classes=[IsAuthenticated])
    def get_social_media_types(self, request):
        try:
            used_social_media = SocialMediaLink.objects.filter(
                content_type=ContentType.objects.get_for_model(request.user.__class__),
                object_id=request.user.id
            ).values_list('social_media_type', flat=True)
            available_types = SocialMediaType.objects.filter(is_active=True).exclude(id__in=used_social_media)
            serializer = SocialMediaTypeSerializer(available_types, many=True)
            return Response(serializer.data, status=200)
        except Exception as e:
            return Response({"error": "Failed to fetch social media types."}, status=500)