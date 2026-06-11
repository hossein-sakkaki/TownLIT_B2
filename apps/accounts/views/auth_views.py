# apps/accounts/views/auth_views.py

from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from django.conf import settings
from django.db import IntegrityError, transaction
import datetime
import traceback
import re
import base64
import secrets
from django.db.models import Q


from datetime import timedelta
from apps.accounts.constants.user_labels import (
    BELIEVER,
    SEEKER,
    PREFER_NOT_TO_SAY,
    YOUNG_PATH,
    ACTIVE_USER_LABEL_KEYS,
    YOUNG_PATH_COMING_SOON_MESSAGE,
)
from apps.accounts.models import user
from apps.core.crypto import rsa as crsa

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny    
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError

from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from cryptography.fernet import Fernet

from apps.accounts.models.user import CustomUser
from apps.accounts.models.labels import CustomLabel
from apps.accounts.models.invite import InviteCode
from apps.accounts.models.devices import UserDeviceKey, UserDeviceKeyBackup, UserSecurityProfile

from apps.main.services.policy_acceptance import accept_required_policies
from utils.security.security_manager import SecurityStateManager
# Auth serializers
from apps.accounts.serializers.auth_serializers import (
    RegisterUserSerializer,
    LoginSerializer,
    VerifyNewBornSerializer,
    ForgetPasswordSerializer,
    ResetPasswordSerializer,
)

# User serializers
from apps.accounts.serializers.user_serializers import (
    CustomUserAuthSerializer,
    CustomUserSerializer,
    ReactivationUserSerializer,
)

# Device serializers
from apps.accounts.serializers.device_serializers import (
    UserDeviceKeySerializer,
)

from apps.accounts.tasks.onboarding_tasks import send_believer_welcome_email
from apps.profiles.models import Member, GuestUser
from apps.conversation.models import Message, MessageEncryption
from apps.communication.models import ExternalContact
from utils.common.utils import create_active_code
from utils.common.ip import get_client_ip, get_location_from_ip
from utils.email.email_tools import send_custom_email
from utils.security.destructive_actions import handle_destructive_pin_actions
import utils as utils
import logging
from django.contrib.auth import get_user_model
from apps.accounts.utils.country import normalize_profile_country

CustomUser = get_user_model()
logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security.identity")


# Generate key for encryption ---------------------------------------------------
cipher_suite = Fernet(settings.FERNET_KEY)


# Encryption --------------------------------------------------------------------
def encrypt_active_code_for_storage(active_code) -> str:
    """
    Fernet returns bytes. Store it as a clean string in DB/session.
    """
    return cipher_suite.encrypt(str(active_code).encode()).decode()


def decrypt_active_code_from_storage(encrypted_value) -> str:
    """
    Accepts values from session or DB.

    Handles:
    - clean Fernet string: gAAAA...
    - bytes
    - legacy string accidentally saved like: b'gAAAA...'
    """
    if encrypted_value is None:
        raise ValueError("Missing encrypted activation code.")

    if isinstance(encrypted_value, bytes):
        token = encrypted_value
    else:
        token_text = str(encrypted_value).strip()

        # Legacy safety: CharField may have stored bytes as "b'...'"
        if (
            len(token_text) >= 3
            and token_text.startswith("b'")
            and token_text.endswith("'")
        ):
            token_text = token_text[2:-1]

        if (
            len(token_text) >= 3
            and token_text.startswith('b"')
            and token_text.endswith('"')
        ):
            token_text = token_text[2:-1]

        token = token_text.encode()

    return cipher_suite.decrypt(token).decode()


def get_registration_id_from_request(request, serializer=None) -> str:
    if serializer is not None:
        value = serializer.validated_data.get("registration_id")
        if value:
            return str(value).strip()

    return str(request.data.get("registration_id") or "").strip()

# -------------------------------------------------------------------------------
def _get_pop_ttl_minutes():
    raw = getattr(settings, "POP_TTL_MINUTES", 10)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 10

# داخل register_device_key:
POP_TTL_MINUTES = _get_pop_ttl_minutes()

# Normalize PEM: strip headers/footers and all whitespace, then base64-decode → DER bytes -----------
def _pem_to_der_bytes(pem: str) -> bytes:
    cleaned = re.sub(r"-----(BEGIN|END) PUBLIC KEY-----|\s+", "", pem or "")
    return base64.b64decode(cleaned) if cleaned else b""


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
    # Throttling (scoped)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "crypto"  # default scope

    # Whitelists for our global permission
    allow_deleted_actions = {"send_reactivate_confirmation", "confirm_reactivate_account"}
    allow_suspended_actions = {"logout"}

    def get_throttles(self):
        heavy_actions = {"backfill_device_keys"}
        self.throttle_scope = "crypto_heavy" if getattr(self, "action", None) in heavy_actions else "crypto"
        return super().get_throttles()
    
    # Country Inference for Registration -------------------------------
    def _infer_registration_country(self, request):
        """
        Best-effort country inference for initial profile prefill.

        Priority:
        1) Explicit client value from body
        2) Optional app/device headers
        3) CDN/proxy country headers
        4) IP geolocation fallback

        This must never be treated as verified identity data.
        """
        candidates = [
            request.data.get("country"),
            request.data.get("device_country"),
            request.headers.get("X-Device-Country"),
            request.headers.get("X-App-Country"),
            request.headers.get("CloudFront-Viewer-Country"),
            request.headers.get("CF-IPCountry"),
        ]

        for value in candidates:
            country = normalize_profile_country(value)
            if country:
                return country

        ip_address = get_client_ip(request)
        location = get_location_from_ip(ip_address) or {}

        for value in [
            location.get("country_code"),
            location.get("countryCode"),
            location.get("country"),
        ]:
            country = normalize_profile_country(value)
            if country:
                return country

        return None

    # Source of Truth -------------------------
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="me"
    )
    def me(self, request):
        """
        🔐 Source of Truth for authenticated user
        Read-only endpoint
        """
        user = request.user

        serializer = CustomUserAuthSerializer(
            user,
            context={"request": request}
        )

        return Response(serializer.data, status=200)
    
    # Register -------------------------------
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
                    if ser_data.is_valid():
                        existing_user.set_password(ser_data.validated_data["password"])
                        existing_user.user_active_code = None
                        existing_user.user_active_code_expiry = None
                        existing_user.registration_started_at = timezone.now()
                        existing_user.registration_id = secrets.token_urlsafe(32)

                        update_fields = [
                            "password",
                            "user_active_code",
                            "user_active_code_expiry",
                            "registration_started_at",
                            "registration_id",
                        ]

                        if not existing_user.country:
                            inferred_country = self._infer_registration_country(request)
                            if inferred_country:
                                existing_user.country = inferred_country
                                update_fields.append("country")

                        existing_user.save(update_fields=update_fields)

                        # choose language
                        lang = (request.data.get("language") or "en").strip().lower()

                        with transaction.atomic():
                            accept_required_policies(
                                user=existing_user,
                                acceptance_context="registration",
                                language=lang,
                            )

                        # Generate and encrypt activation code ---------
                        active_code = create_active_code(5)
                        expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
                        expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
                        encrypted_active_code = encrypt_active_code_for_storage(active_code)
                        existing_user.user_active_code = encrypted_active_code
                        existing_user.user_active_code_expiry = expiration_time
                        existing_user.save(update_fields=[
                            "user_active_code",
                            "user_active_code_expiry",
                        ])
                        
                        print('----------------------1----------------------')
                        print(active_code)
                        print('-----------------------1---------------------')

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
                            'active_code': encrypted_active_code,
                            'user_id': existing_user.id,
                            'registration_id': existing_user.registration_id,
                            'forget_password': False,
                        }
                        request.session.modified = True
                        request.session.save()

                        return Response({
                            "message": "Existing account updated. Please verify the new code.",
                            "redirect_to_verify": True,
                            "registration_id": existing_user.registration_id,
                        }, status=status.HTTP_200_OK)
                    else:
                        return Response({"message": extract_first_error_message(ser_data.errors)}, status=status.HTTP_400_BAD_REQUEST)

            # Create new user
            if ser_data.is_valid():
                inferred_country = self._infer_registration_country(request)

                user = CustomUser.objects.create_user(
                    email=ser_data.validated_data["email"],
                    password=ser_data.validated_data["password"],
                    country=inferred_country,
                )

                user.registration_id = secrets.token_urlsafe(32)
                user.save(update_fields=["registration_id"])

                # choose language
                lang = (request.data.get("language") or "en").strip().lower()

                with transaction.atomic():
                    accept_required_policies(
                        user=user,
                        acceptance_context="registration",
                        language=lang,
                    )

                # Generate and encrypt activation code ---------
                active_code = create_active_code(5)
                expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
                expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)
                encrypted_active_code = encrypt_active_code_for_storage(active_code)
                user.user_active_code = encrypted_active_code
                user.user_active_code_expiry = expiration_time
                user.save(update_fields=[
                    "user_active_code",
                    "user_active_code_expiry",
                ])
                
                print('----------------------2----------------------')
                print(active_code)
                print('----------------------2----------------------')
                    
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
                    'active_code': encrypted_active_code,
                    'user_id': user.id,
                    'registration_id': user.registration_id,
                    'forget_password': False,
                }
                request.session.modified = True
                request.session.save()

                return Response({
                    "message": "User registered successfully and profile created.",
                    "redirect_to_verify": True,
                    "registration_id": user.registration_id,
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

    # Verify --------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verify(self, request):
        ser_data = VerifyNewBornSerializer(data=request.data)

        if not ser_data.is_valid():
            return Response(
                {"message": extract_first_error_message(ser_data.errors)},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_session = request.session.get('user_session')
        registration_id = get_registration_id_from_request(
            request,
            serializer=ser_data,
        )

        user = None
        encrypted_active_code = None

        # ------------------------------------------------------------
        # 1) Web/session flow
        # ------------------------------------------------------------
        if user_session:
            encrypted_active_code = user_session.get('active_code')

            if not encrypted_active_code:
                return Response(
                    {
                        "error": "No activation code found in session. Please try registering again.",
                        "code": "activation_code_not_found",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                user = CustomUser.objects.get(id=user_session['user_id'])
            except CustomUser.DoesNotExist:
                return Response(
                    {
                        "error": "User not found.",
                        "code": "user_not_found",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ------------------------------------------------------------
        # 2) Mobile fallback flow
        # ------------------------------------------------------------
        elif registration_id:
            try:
                user = CustomUser.objects.get(
                    registration_id=registration_id,
                    is_active=False,
                    is_deleted=False,
                )
            except CustomUser.DoesNotExist:
                return Response(
                    {
                        "error": "Registration session was not found or has expired. Please register again.",
                        "code": "registration_session_not_found",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            encrypted_active_code = user.user_active_code

            if not encrypted_active_code:
                return Response(
                    {
                        "error": "No activation code found. Please register again.",
                        "code": "activation_code_not_found",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ------------------------------------------------------------
        # 3) No session and no registration_id
        # ------------------------------------------------------------
        else:
            return Response(
                {
                    "error": "Session data not found. Please try registering again.",
                    "code": "registration_session_missing",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Expiry check before decrypt/compare
        # ------------------------------------------------------------
        if user.user_active_code_expiry and timezone.now() > user.user_active_code_expiry:
            return Response(
                {
                    "error": "Activation code has expired. Please register again.",
                    "code": "activation_code_expired",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Decrypt activation code
        # ------------------------------------------------------------
        try:
            decrypted_active_code = decrypt_active_code_from_storage(
                encrypted_active_code
            )
        except Exception as e:
            logger.exception(
                "Activation code decrypt failed for user_id=%s registration_id_present=%s",
                getattr(user, "id", None),
                bool(registration_id),
            )
            return Response(
                {
                    "error": "An error occurred while processing your activation code. Please try registering again.",
                    "code": "activation_code_decrypt_failed",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if decrypted_active_code != ser_data.validated_data['active_code']:
            return Response(
                {
                    "error": "Incorrect activation code. Please check and try again.",
                    "code": "incorrect_activation_code",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Mark email verified but keep user inactive until choose-path.
        # Keep registration_id until choose-path completes for mobile.
        # ------------------------------------------------------------
        user.user_active_code = None
        user.user_active_code_expiry = None
        user.is_active = False
        user.save(update_fields=[
            "user_active_code",
            "user_active_code_expiry",
            "is_active",
        ])

        # Keep a lightweight session for web choose-path.
        request.session['user_session'] = {
            'user_id': user.id,
            'registration_id': user.registration_id,
            'verified': True,
            'forget_password': False,
        }
        request.session.modified = True

        return Response(
            {
                "message": "User verified successfully. Please answer the category questions.",
                "redirect_to_choose_path": True,
                "registration_id": user.registration_id,
            },
            status=status.HTTP_200_OK
        )
    
    # Verify Password (for sensitive operations) ---------------------------------------------------
    @action(detail=False, methods=["post"], url_path="verify-password", permission_classes=[IsAuthenticated])
    def verify_password(self, request):
        """
        Verify the user's current password before allowing sensitive operations (e.g. reset key).
        Expected body:
            { "password": "current_password" }

        Returns:
            200 OK  → { "valid": true }
            400 Bad Request → { "valid": false, "error": "Invalid password" }
        """
        user = request.user
        password = request.data.get("password", "")

        if not password:
            return Response(
                {"valid": False, "error": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Use Django's built-in password checker (hashed verification)
        from django.contrib.auth.hashers import check_password

        if check_password(password, user.password):
            return Response({"valid": True}, status=status.HTTP_200_OK)

        # Wrong password: minimal info (no hints)
        return Response(
            {"valid": False, "error": "Invalid password."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Choose Path (for onboarding) ---------------------------------------------------
    @action(detail=False, methods=['post'], url_path='choose-path', permission_classes=[AllowAny])
    def choose_path(self, request):
        """
        Complete onboarding after email verification.

        Supports:
        - Web flow: Django session user_session
        - iOS/mobile flow: registration_id in request body

        Important:
        - registration_id must remain alive after verify and be cleared only after
          choose-path succeeds.
        - user stays inactive until choose-path completes.
        """

        user_session = request.session.get('user_session')
        registration_id = get_registration_id_from_request(request)

        user = None

        # ------------------------------------------------------------
        # Resolve pending verified user
        # ------------------------------------------------------------
        if user_session:
            try:
                user = CustomUser.objects.get(id=user_session['user_id'])
            except CustomUser.DoesNotExist:
                return Response(
                    {
                        "error": "User not found.",
                        "code": "user_not_found",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        elif registration_id:
            try:
                user = CustomUser.objects.get(
                    registration_id=registration_id,
                    is_active=False,
                    is_deleted=False,
                )
            except CustomUser.DoesNotExist:
                return Response(
                    {
                        "error": "Registration session not found. Please register again.",
                        "code": "registration_session_not_found",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        else:
            return Response(
                {
                    "error": "Session data not found",
                    "code": "registration_session_missing",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Must be verified before choosing path
        # ------------------------------------------------------------
        if user.user_active_code:
            return Response(
                {
                    "error": "Please verify your email before choosing a profile path.",
                    "code": "email_verification_required",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Category validation
        # ------------------------------------------------------------
        category = (request.data.get('category') or "").strip().lower()

        if category == YOUNG_PATH:
            return Response(
                {
                    "error": YOUNG_PATH_COMING_SOON_MESSAGE,
                    "code": "young_path_coming_soon",
                    "profile_type": None,
                    "can_create_profile": False,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not category or category not in ACTIVE_USER_LABEL_KEYS:
            return Response(
                {
                    "error": "Invalid category",
                    "code": "invalid_profile_path",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Retrieve the appropriate label
        # ------------------------------------------------------------
        try:
            label = CustomLabel.objects.get(name=category)
        except CustomLabel.DoesNotExist:
            return Response(
                {
                    "error": "Label not found.",
                    "code": "label_not_found",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Assign label and profile type to user
        # ------------------------------------------------------------
        user.label = label
        user.is_member = (category == BELIEVER)

        try:
            user.save(update_fields=["label", "is_member"])

            external_contact = ExternalContact.objects.filter(
                email__iexact=user.email
            ).first()

            if external_contact:
                external_contact.became_user = True
                external_contact.became_user_at = timezone.now()
                external_contact.deleted_after_signup = False
                external_contact.save(update_fields=[
                    "became_user",
                    "became_user_at",
                    "deleted_after_signup",
                ])

        except Exception as e:
            logger.exception("Unable to save user onboarding label/profile type")
            return Response(
                {
                    "error": "Unable to save user data. Please try again.",
                    "details": str(e),
                    "code": "user_onboarding_save_failed",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------
        # Create or activate profile based on category
        # ------------------------------------------------------------
        if category == BELIEVER:
            try:
                member_instance, created = Member.objects.get_or_create(
                    user=user
                )

                member_instance.is_active = True
                member_instance.is_migrated = False
                member_instance.save(
                    update_fields=["is_active", "is_migrated"]
                )

                # If a guest profile already exists, keep it inactive.
                GuestUser.objects.filter(user=user).update(
                    is_active=False,
                    is_migrated=True,
                )

            except Exception as e:
                logger.exception("Unable to create/activate member profile")
                return Response(
                    {
                        "error": "Unable to create member profile. Please try again later or contact support.",
                        "details": str(e),
                        "code": "member_profile_create_failed",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        else:
            try:
                guest_user_instance, created = GuestUser.objects.get_or_create(
                    user=user
                )

                guest_user_instance.is_active = True
                guest_user_instance.is_migrated = False
                guest_user_instance.save(
                    update_fields=["is_active", "is_migrated"]
                )

                # If a member profile already exists, keep it inactive.
                Member.objects.filter(user=user).update(
                    is_active=False,
                    is_migrated=True,
                )

            except Exception as e:
                logger.exception("Unable to create/activate guest profile")
                return Response(
                    {
                        "error": "Unable to create guest user profile. Please try again later or contact support.",
                        "details": str(e),
                        "code": "guest_profile_create_failed",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ------------------------------------------------------------
        # Activate user and clear one-time registration token
        # ------------------------------------------------------------
        user.last_login = timezone.now()
        user.is_active = True
        user.registration_id = None
        user.save(update_fields=[
            "last_login",
            "is_active",
            "registration_id",
        ])

        # Clean up Django session when present.
        try:
            request.session.pop("user_session", None)
            request.session.modified = True
        except Exception:
            pass

        # Fire async welcome email only for member/believer
        if user.is_member:
            try:
                send_believer_welcome_email.delay(user.id)
            except Exception as e:
                logger.warning(f"Welcome email task failed to dispatch: {str(e)}")

        # Mark invite code as used only after successful onboarding
        if getattr(settings, 'USE_INVITE_CODE', False):
            try:
                invite = InviteCode.objects.filter(
                    email__iexact=user.email,
                    used_by__isnull=True
                ).first()

                if invite:
                    invite.mark_as_used(user)

            except Exception as e:
                logger.warning(f"Failed to mark invite as used: {str(e)}")

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        user_data = CustomUserSerializer(
            user,
            context={"request": request}
        ).data

        return Response(
            {
                "refresh": str(refresh),
                "access": str(access),
                "is_member": user.is_member,
                "user": user_data,
                "message": "Profile created successfully based on the provided category. Welcome to TownLIT!",
                "note": "Feel free to complete your profile or start exploring.",
            },
            status=status.HTTP_200_OK
        )
        
    # Login ----------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        ser_data = LoginSerializer(data=request.data)

        if not ser_data.is_valid():
            return Response(
                {"error": extract_first_error_message(ser_data.errors)},
                status=status.HTTP_400_BAD_REQUEST
            )

        identifier = ser_data.validated_data["identifier"]

        # 1) find user by email OR username
        # Keep user-facing message uniform to avoid account enumeration.
        try:
            user = (
                CustomUser.objects
                .select_related("label")
                .get(
                    Q(email__iexact=identifier) |
                    Q(username__iexact=identifier)
                )
            )
        except CustomUser.DoesNotExist:
            return Response({
                "message": "We couldn't find an account with this email or username. If you're new, consider joining the family!"
            }, status=status.HTTP_401_UNAUTHORIZED)
        except CustomUser.MultipleObjectsReturned:
            logger.error(
                "Multiple users matched login identifier=%s",
                identifier,
            )
            return Response({
                "message": "We could not process this login. Please contact support."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2) verify password first
        if not user.check_password(ser_data.validated_data['password']):
            return Response({
                "message": "Hmm... that password didn’t match. Please try again — and don’t worry, it happens!"
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 3) hard-deleted flow
        if user.is_deleted:
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            react_user = ReactivationUserSerializer(
                user,
                context={"request": request}
            ).data

            return Response({
                "message": "Your account deletion request is in progress. You can reactivate your account within 1 year.",
                "reactivation_required": True,
                "is_deleted": True,
                "deletion_requested_at": user.deletion_requested_at,
                "email": user.email,
                "user_id": user.id,
                "refresh": str(refresh),
                "access": str(access),
                "user": react_user,
            }, status=status.HTTP_202_ACCEPTED)

        # 4) suspended -> block login
        if getattr(user, "is_suspended", False):
            return Response({
                "message": (
                    "Your account is temporarily suspended for a LITSanctuary review. "
                    "This protective step helps keep you and the community safe. "
                    "Access may be restored once the review completes."
                ),
                "is_suspended": True,
                "email": user.email,
            }, status=status.HTTP_423_LOCKED)

        # 5) inactive -> block
        if not user.is_active:
            return Response({
                "message": "User account is not active. Please verify your email or contact support."
            }, status=status.HTTP_403_FORBIDDEN)

        # 6) 2FA flow
        if user.two_factor_enabled:
            otp_code = user.generate_two_factor_token()
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES

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
                return Response(
                    {"error": "Failed to send OTP email. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response({
                "message": "Two-factor authentication required. Please check your email for the OTP code.",
                "two_factor_enabled": user.two_factor_enabled,
                # IMPORTANT:
                # Return canonical email so mobile can complete 2FA even if login started with username.
                "email": user.email,
            }, status=status.HTTP_202_ACCEPTED)

        # 7) success
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        user_data = CustomUserSerializer(
            user,
            context={"request": request}
        ).data

        return Response({
            'refresh': str(refresh),
            'access': str(access),
            'is_member': user.is_member,
            'two_factor_enabled': user.two_factor_enabled,
            'user': user_data,
            'user_id': user.id,
            'email': user.email,
        }, status=status.HTTP_200_OK)

    # Login with 2FA ----------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='login-with-2fa', permission_classes=[AllowAny])
    def login_with_2fa(self, request):
        identifier = (
            request.data.get('email')
            or request.data.get('identifier')
            or request.data.get('username')
            or ""
        ).strip()
        otp_code = (request.data.get('otp_code') or "").strip()

        if not identifier or not otp_code:
            return Response({
                "message": "Email or username and OTP code are required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = (
                CustomUser.objects
                .select_related("label")
                .get(
                    Q(email__iexact=identifier) |
                    Q(username__iexact=identifier)
                )
            )
        except CustomUser.DoesNotExist:
            return Response({
                "message": "User with this email or username does not exist."
            }, status=status.HTTP_404_NOT_FOUND)
        except CustomUser.MultipleObjectsReturned:
            logger.error(
                "Multiple users matched 2FA login identifier=%s",
                identifier,
            )
            return Response({
                "message": "We could not process this login. Please contact support."
            }, status=status.HTTP_400_BAD_REQUEST)

        if getattr(user, "is_suspended", False):
            return Response({
                "message": (
                    "Your account is temporarily suspended for a LITSanctuary review. "
                    "This protective step helps keep you and the community safe. "
                    "Access may be restored once the review completes."
                ),
                "is_suspended": True,
                "email": user.email,
            }, status=status.HTTP_423_LOCKED)

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

            if user.is_deleted:
                react_user = ReactivationUserSerializer(
                    user,
                    context={"request": request}
                ).data

                return Response({
                    "message": "Account deactivated. You can reactivate within 1 year using the code sent to your email.",
                    "reactivation_required": True,
                    "is_deleted": True,
                    "deletion_requested_at": user.deletion_requested_at,
                    "email": user.email,
                    "user_id": user.id,
                    "refresh": str(refresh),
                    "access": str(access),
                    "user": react_user,
                }, status=status.HTTP_202_ACCEPTED)

            user_data = CustomUserSerializer(
                user,
                context={"request": request}
            ).data

            return Response({
                'refresh': str(refresh),
                'access': str(access),
                'is_member': user.is_member,
                'user': user_data,
                'user_id': user.id,
                'email': user.email,
            }, status=status.HTTP_200_OK)

        if token_status == "expired":
            return Response({
                "message": "Your OTP code has expired. Please request a new one."
            }, status=status.HTTP_400_BAD_REQUEST)

        if token_status == "no_token":
            return Response({
                "message": "No OTP code was generated. Please start the login process again."
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Invalid OTP code. Please try again."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Logout ---------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="logout", permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        Revoke refresh token and force WS logout for THIS device only.

        Logout is intentionally idempotent:
        even if the refresh token is missing, invalid, or already blacklisted,
        the client should still be allowed to clear its local session.
        """
        refresh_token = request.data.get("refresh")

        # Read device_id used by WS querystring.
        device_id = (request.data.get("device_id") or "").strip().lower()

        token_revoked = False
        token_status = "missing"

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)

                try:
                    token.blacklist()
                    token_revoked = True
                    token_status = "revoked"
                except Exception:
                    # Already blacklisted or blacklist app edge case.
                    token_status = "already_revoked_or_unavailable"

            except TokenError:
                # Do not block logout because token is already invalid/expired.
                token_status = "invalid_or_expired"

        # Best-effort WS force logout.
        if device_id:
            try:
                channel_layer = get_channel_layer()

                if channel_layer is not None:
                    async_to_sync(channel_layer.group_send)(
                        f"device_{device_id}",
                        {
                            "type": "dispatch_event",
                            "app": "conversation",
                            "event": "force_logout",
                            "data": {
                                "user_id": request.user.id,
                                "device_id": device_id,
                            },
                        },
                    )
            except Exception:
                # Logout must not fail because realtime cleanup failed.
                pass

        return Response(
            {
                "message": "User has been successfully logged out.",
                "token_revoked": token_revoked,
                "token_status": token_status,
            },
            status=status.HTTP_200_OK,
        )

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
                reset_link = f'{settings.SITE_URL}/reset-password/{reset_token}/' 
                
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
            user_data = CustomUserSerializer(user, context={"request": request}).data

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
                return Response({"error": "Failed to send OTP email. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)            
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
                return Response({"error": "Failed to send OTP email. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        
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
        user = request.user

        # -----------------------------
        # LITShield authorization check
        # -----------------------------
        litshield = getattr(user, "litshield_grant", None)
        if not litshield or not litshield.is_active:
            return Response(
                {"error": "LITShield access is not granted for this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        access_pin = request.data.get("access_pin")
        delete_pin = request.data.get("delete_pin")

        # -----------------------------
        # Validation
        # -----------------------------
        if not access_pin or not delete_pin:
            return Response(
                {"error": "Both access_pin and delete_pin are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(access_pin) != 4 or not access_pin.isdigit():
            return Response(
                {"error": "Access pin must be exactly 4 numeric digits."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(delete_pin) != 4 or not delete_pin.isdigit():
            return Response(
                {"error": "Delete pin must be exactly 4 numeric digits."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if access_pin == delete_pin:
            return Response(
                {"error": "Access pin and delete pin must be different."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -----------------------------
        # Set pins
        # -----------------------------
        user.set_access_pin(access_pin)
        user.set_delete_pin(delete_pin)

        user.pin_security_enabled = True
        user.save(update_fields=["access_pin", "delete_pin", "pin_security_enabled"])

        return Response(
            {"message": "PIN security enabled successfully."},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], url_path='disable-pin', permission_classes=[IsAuthenticated])
    def disable_pin(self, request):
        try:
            user = request.user
            entered_pin = request.data.get('pin')            
            if not entered_pin:
                return Response({"error": "Pin is required to disable pin security."}, status=status.HTTP_400_BAD_REQUEST)

            if user.verify_access_pin(entered_pin):
                SecurityStateManager.unhide_confidants(user)
                user.access_pin = None
                user.delete_pin = None
                user.pin_security_enabled = False
                user.save()
                return Response({"message": "Security pins removed and pin security disabled."}, status=status.HTTP_200_OK)

            elif user.verify_delete_pin(entered_pin):
                handle_destructive_pin_actions(user)
                user.access_pin = None
                user.delete_pin = None
                user.pin_security_enabled = False
                user.save()
                return Response({"message": "Security pins removed, pin security disabled, and all messages deleted."}, status=status.HTTP_200_OK)
            return Response({"error": "Invalid pin entered."}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ---------------------------------------------------------------------------------------------------------------
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
                return Response({"error": "Failed to send confirmation email. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        
    # ----------------------------------------------------------------------------------------------------        
    @action(detail=False, methods=['post'], url_path='send-reactivate-confirmation', permission_classes=[IsAuthenticated])
    def send_reactivate_confirmation(self, request):
        try:
            user = request.user
            if not user.is_deleted:
                return Response({"error": "Your account is not marked for deletion."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate and store OTP (encrypted)
            active_code = create_active_code(5)
            expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
            expiration_time = timezone.now() + datetime.timedelta(minutes=expiration_minutes)

            encrypted_active_code = cipher_suite.encrypt(str(active_code).encode())
            user.user_active_code = encrypted_active_code.decode()
            user.user_active_code_expiry = expiration_time
            user.save(update_fields=["user_active_code", "user_active_code_expiry"])

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
                text_template_path=None
            )
            if not success:
                return Response({"error": "Failed to send reactivation code. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

            # Decrypt and validate
            try:
                decrypted_active_code = cipher_suite.decrypt(user.user_active_code.encode()).decode()
            except Exception:
                return Response({"error": "Failed to decrypt the reactivation code."}, status=status.HTTP_400_BAD_REQUEST)
            if decrypted_active_code != code:
                return Response({"error": "Invalid reactivation code."}, status=status.HTTP_400_BAD_REQUEST)
            if user.user_active_code_expiry and timezone.now() > user.user_active_code_expiry:
                return Response({"error": "The reactivation code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            # Reactivate
            user.is_deleted = False
            user.deletion_requested_at = None
            user.user_active_code = None
            user.user_active_code_expiry = None
            user.reactivated_at = timezone.now()
            user.save(update_fields=[
                "is_deleted", "deletion_requested_at",
                "user_active_code", "user_active_code_expiry",
                "reactivated_at"
            ])

            external_contact = ExternalContact.objects.filter(email__iexact=user.email).first()
            if external_contact:
                external_contact.became_user = True
                external_contact.became_user_at = timezone.now()
                external_contact.deleted_after_signup = False
                external_contact.save(update_fields=["became_user", "became_user_at", "deleted_after_signup"])

            # Email success
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
                return Response({"error": "Reactivated, but failed to send confirmation email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({"message": "Your account has been successfully reactivated."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in confirm_reactivate_account: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Register Device Key ----------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="register-device-key", permission_classes=[IsAuthenticated])
    def register_device_key(self, request):
        """
        Register/rotate a device public key + (NEW: push token support).

        Policy:
        - device_id MUST be the key-fingerprint (canonical).
        - Dedup Plan A: install_id (stable per install) → remove old rows of same install.
        - Dedup Plan B: fingerprint_hint + replace_same_fp=True.
        - Both A and B may run; do NOT use elif.
        """
        user = request.user

        # ----- Inputs -----
        device_id = (request.data.get("device_id") or "").strip().lower()
        public_key = request.data.get("public_key")
        device_name = request.data.get("device_name")
        allow_rotate = bool(request.data.get("allow_rotate", False))

        # PUSH TOKEN (NEW)
        push_token = request.data.get("push_token") or None
        platform = request.data.get("platform") or None

        # ----- install_id -----
        body_install = (request.data.get("install_id") or "").strip().lower()
        header_install = (request.headers.get("X-Install-ID") or "").strip().lower()
        install_id = body_install or header_install or None

        # ----- Plan-B hint -----
        fingerprint_hint = (request.data.get("fingerprint_hint") or "").strip()
        replace_same_fp = str(request.data.get("replace_same_fp", "")).lower() in ("1", "true", "yes", "on")

        # ----- Consistency checks -----
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
        if header_device and header_device != device_id:
            return Response({"error": "X-Device-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        if body_install and header_install and body_install != header_install:
            return Response({"error": "X-Install-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        user_agent = request.META.get("HTTP_USER_AGENT", "") or ""
        ip_address = get_client_ip(request)

        # ----- Basic validation -----
        if not device_id or not public_key:
            return Response({"error": "Device ID and public key are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if "-----BEGIN PUBLIC KEY-----" not in public_key or "-----END PUBLIC KEY-----" not in public_key:
            return Response({"error": "Invalid public key format (PEM expected)."},
                            status=status.HTTP_400_BAD_REQUEST)

        # ----- Geo -----
        location = get_location_from_ip(ip_address) or {}
        city = location.get("city")
        region = location.get("region")
        country = location.get("country")
        timezone_str = location.get("timezone")
        organization = location.get("org")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        postal = location.get("postal")

        profile_country = normalize_profile_country(
            location.get("country_code")
            or location.get("countryCode")
            or country
        )

        # ----- Limits -----
        try:
            MAX_ACTIVE_DEVICE_KEYS = int(getattr(settings, "MAX_ACTIVE_DEVICE_KEYS", 10))
        except Exception:
            MAX_ACTIVE_DEVICE_KEYS = 10

        try:
            POP_TTL_MINUTES = int(getattr(settings, "POP_TTL_MINUTES", 10))
        except Exception:
            POP_TTL_MINUTES = 10

        pop_payload = None
        dedup_removed_ids = []
        created = False
        rotated = False

        # =====================================================================================
        # TRANSACTION START
        # =====================================================================================
        with transaction.atomic():

            # ----- Lock this device_id for this user -----
            existing = (
                UserDeviceKey.objects
                .select_for_update(of=("self",))
                .filter(user=user, device_id=device_id)
                .first()
            )

            # =================================================================================
            # 1) EXISTING DEVICE → UPDATE
            # =================================================================================
            if existing:
                old_der = _pem_to_der_bytes(existing.public_key)
                new_der = _pem_to_der_bytes(public_key)

                if old_der != new_der:
                    if not allow_rotate:
                        return Response(
                            {
                                "error": "Public key mismatch for this device_id.",
                                "code": "KEY_MISMATCH",
                                "detail": (
                                    "This device_id is already registered with a different public key. "
                                    "If you intend to rotate keys, re-send with allow_rotate=true. "
                                    "Old E2EE messages may no longer be decryptable after rotation."
                                ),
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    existing.public_key = public_key
                    rotated = True

                # Update metadata
                existing.device_name = device_name or existing.device_name
                existing.user_agent = user_agent
                existing.ip_address = ip_address
                existing.last_used = timezone.now()
                existing.is_active = True
                existing.location_city = city
                existing.location_region = region
                existing.location_country = country
                existing.timezone = timezone_str
                existing.organization = organization
                existing.latitude = latitude
                existing.longitude = longitude
                existing.postal_code = postal

                if install_id:
                    existing.install_id = install_id
                if fingerprint_hint:
                    existing.fp_hint = fingerprint_hint

                # NEW: store push_token/platform
                if push_token:
                    existing.push_token = push_token
                if platform:
                    existing.platform = platform

                existing.save(update_fields=[
                    "public_key", "device_name", "user_agent", "ip_address",
                    "last_used", "is_active",
                    "location_city", "location_region", "location_country", "timezone",
                    "organization", "latitude", "longitude", "postal_code",
                    "install_id", "fp_hint",
                    "push_token", "platform",  # NEW
                ])

                device_obj = existing

            # =================================================================================
            # 2) CREATE NEW DEVICE
            # =================================================================================
            else:
                active_count = UserDeviceKey.objects.filter(user=user, is_active=True).count()

                # Possible rows to remove
                would_remove_ids = set()

                if install_id:
                    ids = UserDeviceKey.objects.filter(user=user, install_id=install_id).values_list("id", flat=True)
                    would_remove_ids.update(ids)

                if replace_same_fp and fingerprint_hint:
                    ids = UserDeviceKey.objects.filter(user=user, fp_hint=fingerprint_hint).values_list("id", flat=True)
                    would_remove_ids.update(ids)

                if active_count >= MAX_ACTIVE_DEVICE_KEYS and (active_count - len(would_remove_ids)) >= MAX_ACTIVE_DEVICE_KEYS:
                    return Response(
                        {"error": "Active device limit reached.", "limit": MAX_ACTIVE_DEVICE_KEYS},
                        status=status.HTTP_403_FORBIDDEN
                    )

                try:
                    device_obj = UserDeviceKey.objects.create(
                        user=user,
                        device_id=device_id,
                        public_key=public_key,
                        device_name=device_name,
                        user_agent=user_agent,
                        ip_address=ip_address,
                        is_active=True,
                        location_city=city,
                        location_region=region,
                        location_country=country,
                        timezone=timezone_str,
                        organization=organization,
                        latitude=latitude,
                        longitude=longitude,
                        postal_code=postal,
                        install_id=install_id,
                        fp_hint=fingerprint_hint or None,

                        # NEW
                        push_token=push_token,
                        platform=platform,
                    )
                    created = True

                except IntegrityError:
                    # Lost the race → update existing instead
                    existing = (
                        UserDeviceKey.objects
                        .select_for_update(of=("self",))
                        .get(user=user, device_id=device_id)
                    )

                    old_der = _pem_to_der_bytes(existing.public_key)
                    new_der = _pem_to_der_bytes(public_key)

                    if old_der != new_der and not allow_rotate:
                        return Response(
                            {
                                "error": "Public key mismatch for this device_id.",
                                "code": "KEY_MISMATCH",
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    if old_der != new_der and allow_rotate:
                        existing.public_key = public_key
                        rotated = True

                    existing.device_name = device_name or existing.device_name
                    existing.user_agent = user_agent
                    existing.ip_address = ip_address
                    existing.last_used = timezone.now()
                    existing.is_active = True
                    existing.location_city = city
                    existing.location_region = region
                    existing.location_country = country
                    existing.timezone = timezone_str
                    existing.organization = organization
                    existing.latitude = latitude
                    existing.longitude = longitude
                    existing.postal_code = postal

                    if install_id:
                        existing.install_id = install_id
                    if fingerprint_hint:
                        existing.fp_hint = fingerprint_hint

                    # NEW
                    if push_token:
                        existing.push_token = push_token
                    if platform:
                        existing.platform = platform

                    existing.save(update_fields=[
                        "public_key", "device_name", "user_agent", "ip_address",
                        "last_used", "is_active",
                        "location_city", "location_region", "location_country", "timezone",
                        "organization", "latitude", "longitude", "postal_code",
                        "install_id", "fp_hint",
                        "push_token", "platform",  # NEW
                    ])
                    device_obj = existing

            # =================================================================================
            # PoP Challenge (unchanged)
            # =================================================================================
            issue_pop = created or rotated or (not device_obj.is_verified)
            if issue_pop:
                nonce = crsa.randbytes(32)
                device_obj.pop_challenge_hash = crsa.sha256_bytes(nonce)
                device_obj.pop_challenge_expiry = timezone.now() + timedelta(minutes=POP_TTL_MINUTES)
                device_obj.pop_attempts = 0
                device_obj.is_verified = False
                device_obj.verified_at = None

                device_obj.save(update_fields=[
                    "pop_challenge_hash", "pop_challenge_expiry", "pop_attempts",
                    "is_verified", "verified_at", "last_used",
                ])

                ct = crsa.rsa_oaep_encrypt_with_public_pem(device_obj.public_key, nonce)
                pop_payload = {
                    "ciphertext_b64": crsa.b64e(ct),
                    "expires_at": device_obj.pop_challenge_expiry.isoformat(),
                    "ttl_minutes": POP_TTL_MINUTES,
                }

            # =================================================================================
            # Dedup A: install_id
            # =================================================================================
            if install_id:
                stale_qs = UserDeviceKey.objects.filter(user=user, install_id=install_id).exclude(id=device_obj.id)
                if stale_qs.exists():
                    dedup_removed_ids.extend(list(stale_qs.values_list("device_id", flat=True)))
                    stale_qs.delete()

            # =================================================================================
            # Dedup B: fingerprint_hint
            # =================================================================================
            if replace_same_fp and fingerprint_hint:
                stale_fp_qs = (
                    UserDeviceKey.objects
                    .filter(user=user, fp_hint=fingerprint_hint)
                    .exclude(id=device_obj.id)
                )
                stale_fp_qs = stale_fp_qs.filter(Q(ip_address=ip_address) | Q(is_verified=False))
                if stale_fp_qs.exists():
                    dedup_removed_ids.extend(list(stale_fp_qs.values_list("device_id", flat=True)))
                    stale_fp_qs.delete()

            # =================================================================================
            # Optional profile country fallback
            # =================================================================================
            if not user.country and profile_country:
                user.country = profile_country
                user.save(update_fields=["country"])
                
        # =====================================================================================
        # RESPONSE
        # =====================================================================================
        return Response({
            "message": "Device key registered successfully." if created else "Device key updated.",
            "created": bool(created),
            "rotated": bool(rotated),
            "location": location,
            "pop": pop_payload,
            "dedup_removed": dedup_removed_ids,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # Device Pop Challenge --------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="device-pop-challenge", permission_classes=[IsAuthenticated])
    def device_pop_challenge(self, request):
        user = request.user
        device_id = (request.data.get("device_id") or "").strip().lower()
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
        if header_device and header_device != device_id:
            return Response({"error": "X-Device-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        dev = UserDeviceKey.objects.filter(user=user, device_id=device_id).first()
        if not dev:
            return Response({"error": "Unknown device_id for this user."}, status=status.HTTP_404_NOT_FOUND)

        if dev.is_verified:
            return Response({"pop": None, "verified": True}, status=status.HTTP_200_OK)

        POP_TTL_MINUTES = _get_pop_ttl_minutes()   # ⬅️ ensure local var is defined

        nonce = crsa.randbytes(32)
        dev.pop_challenge_hash = crsa.sha256_bytes(nonce)
        dev.pop_challenge_expiry = timezone.now() + timedelta(minutes=POP_TTL_MINUTES)
        dev.pop_attempts = 0
        dev.save(update_fields=["pop_challenge_hash", "pop_challenge_expiry", "pop_attempts"])

        ct = crsa.rsa_oaep_encrypt_with_public_pem(dev.public_key, nonce)
        return Response({
            "pop": {
                "ciphertext_b64": crsa.b64e(ct),
                "expires_at": dev.pop_challenge_expiry.isoformat(),
                "ttl_minutes": POP_TTL_MINUTES,
            },
            "verified": False
        }, status=status.HTTP_200_OK)

    # Device Pop Verify --------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="device-pop-verify", permission_classes=[IsAuthenticated])
    def device_pop_verify(self, request):
        user = request.user
        device_id = (request.data.get("device_id") or "").strip().lower()
        nonce_b64 = request.data.get("nonce_b64")
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()

        if header_device and header_device != device_id:
            return Response({"error": "X-Device-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        if not nonce_b64:
            return Response({"error": "nonce_b64 required."}, status=status.HTTP_400_BAD_REQUEST)

        dev = UserDeviceKey.objects.filter(user=user, device_id=device_id).first()
        if not dev:
            return Response({"error": "Unknown device_id for this user."}, status=status.HTTP_404_NOT_FOUND)

        if dev.pop_attempts >= 5:
            return Response({"error": "Too many attempts. Request a new challenge."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if not dev.pop_challenge_hash or not dev.pop_challenge_expiry or timezone.now() > dev.pop_challenge_expiry:
            return Response({"error": "Challenge expired. Request a new challenge."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            nonce = crsa.b64d(nonce_b64)
        except Exception:
            dev.pop_attempts += 1
            dev.save(update_fields=["pop_attempts"])
            return Response({"error": "Invalid nonce format."}, status=status.HTTP_400_BAD_REQUEST)

        calc = crsa.sha256_bytes(nonce)
        if not secrets.compare_digest(calc, dev.pop_challenge_hash):
            dev.pop_attempts += 1
            dev.save(update_fields=["pop_attempts"])
            return Response({"error": "Invalid nonce."}, status=status.HTTP_400_BAD_REQUEST)

        # موفق
        dev.is_verified = True
        dev.verified_at = timezone.now()
        dev.pop_challenge_hash = None
        dev.pop_challenge_expiry = None
        dev.pop_attempts = 0
        dev.save(update_fields=["is_verified", "verified_at", "pop_challenge_hash", "pop_challenge_expiry", "pop_attempts"])

        return Response({"ok": True, "verified": True}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="key-backup-save", permission_classes=[IsAuthenticated])
    def key_backup_save(self, request):
        user = request.user
        device_id = (request.data.get("device_id") or "").strip().lower()
        blob = request.data.get("blob")
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()

        if not device_id or not isinstance(blob, dict):
            return Response({"error": "device_id and blob are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: enforce header matches body to avoid confusion
        if header_device and header_device != device_id:
            return Response({"error": "X-Device-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: size limit (e.g., 64KB)
        import json
        if len(json.dumps(blob)) > 64 * 1024:
            return Response({"error": "Backup blob too large."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure this device exists (optional but good)
        if not UserDeviceKey.objects.filter(user=user, device_id=device_id).exists():
            return Response({"error": "Device not registered."}, status=status.HTTP_404_NOT_FOUND)

        # Upsert backup
        obj, created = UserDeviceKeyBackup.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={"blob": blob},
        )
        return Response({"ok": True, "created": created}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="key-backup-fetch", permission_classes=[IsAuthenticated])
    def key_backup_fetch(self, request):
        user = request.user
        device_id = (request.query_params.get("device_id") or "").strip().lower()
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()

        if not device_id:
            return Response({"error": "device_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        if header_device and header_device != device_id:
            return Response({"error": "X-Device-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        obj = UserDeviceKeyBackup.objects.filter(user=user, device_id=device_id).first()
        if not obj:
            return Response({"blob": None}, status=status.HTTP_200_OK)

        return Response({"blob": obj.blob}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="has-key-backup", permission_classes=[IsAuthenticated])
    def has_key_backup(self, request):
        """
        Return whether the current user has an encrypted key backup for the given device_id.
        Response: {"has_backup": true/false}
        """
        user = request.user
        device_id = (request.query_params.get("device_id") or "").strip().lower()
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()

        # Basic validation
        if not device_id:
            return Response({"error": "device_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: enforce header-body consistency
        if header_device and header_device != device_id:
            return Response({"error": "X-Device-ID mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # Lightweight existence check (no blob loading)
        from apps.accounts.models.devices import UserDeviceKeyBackup
        has_backup = UserDeviceKeyBackup.objects.filter(user=user, device_id=device_id).exists()

        return Response({"has_backup": bool(has_backup)}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="passphrase-profile", permission_classes=[IsAuthenticated])
    def passphrase_profile(self, request):
        """
        Returns whether the user has already set a passphrase and (optional) KDF params.
        No passphrase is ever sent/stored server-side.
        """
        from apps.accounts.models.devices import UserSecurityProfile
        prof, _ = UserSecurityProfile.objects.get_or_create(user=request.user)
        return Response({
            "has_passphrase": prof.has_passphrase,
            "kdf": prof.kdf,
            "iterations": prof.iterations,
        }, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="passphrase-profile-set", permission_classes=[IsAuthenticated])
    def passphrase_profile_set(self, request):
        """
        Marks that the user has set a passphrase (after a successful client-side backup).
        Client may optionally send chosen KDF params (non-secret).
        """
        prof, _ = UserSecurityProfile.objects.get_or_create(user=request.user)

        kdf = request.data.get("kdf") or prof.kdf or "PBKDF2"
        iterations = int(request.data.get("iterations") or prof.iterations or 600000)

        prof.kdf = kdf
        prof.iterations = iterations
        prof.has_passphrase = True
        prof.save(update_fields=["has_passphrase", "kdf", "iterations", "updated_at"])

        return Response({"ok": True}, status=status.HTTP_200_OK)
    
    # 1) Do I have any backup across my devices? -----------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="has-any-key-backup", permission_classes=[IsAuthenticated])
    def has_any_key_backup(self, request):
        has_any = UserDeviceKeyBackup.objects.filter(user=request.user).exists()
        return Response({"has_backup": bool(has_any)}, status=status.HTTP_200_OK)

    # 2) Return latest backup blob (regardless of device_id)
    @action(detail=False, methods=["get"], url_path="key-backup-latest", permission_classes=[IsAuthenticated])
    def key_backup_latest(self, request):
        obj = (UserDeviceKeyBackup.objects
            .filter(user=request.user)
            .order_by("-updated_at", "-created_at")
            .first())
        if not obj:
            return Response({"blob": None}, status=status.HTTP_200_OK)
        return Response({"blob": obj.blob, "device_id": obj.device_id}, status=status.HTTP_200_OK)

    # 3) (Optional) List all backup entries for selection UI
    @action(detail=False, methods=["get"], url_path="key-backup-list", permission_classes=[IsAuthenticated])
    def key_backup_list(self, request):
        qs = UserDeviceKeyBackup.objects.filter(user=request.user).order_by("-updated_at", "-created_at")
        items = [{"device_id": x.device_id, "updated_at": x.updated_at} for x in qs]
        return Response({"items": items}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="backfill-device-keys", permission_classes=[IsAuthenticated])
    def backfill_device_keys(self, request):
        """
        Copy existing per-message encryption rows from any of the user's device_ids
        to the provided new device_id, if missing. This makes the device immediately
        able to decrypt past messages after a key restore.
        """
        user = request.user
        new_device_id = (request.data.get("device_id") or "").strip().lower()
        if not new_device_id:
            return Response({"error": "device_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 1) Ensure the target device belongs to this user
        if not UserDeviceKey.objects.filter(user=user, device_id=new_device_id).exists():
            return Response({"error": "Unknown device_id for this user."}, status=status.HTTP_404_NOT_FOUND)

        # 2) Collect all device_ids of this user (including the new one)
        user_device_ids = list(
            UserDeviceKey.objects.filter(user=user).values_list("device_id", flat=True)
        )

        # 3) Gather all message ids the user is allowed to access (their dialogues)
        #    NOTE: if you have very large datasets, consider restricting time range or paging
        message_ids = list(
            Message.objects.filter(dialogue__participants=user)
            .values_list("id", flat=True)
            .distinct()
        )

        if not message_ids:
            return Response({"backfilled": 0, "skipped": 0}, status=status.HTTP_200_OK)

        # 4) Which messages already have an entry for the new_device_id?
        existing_for_new = set(
            MessageEncryption.objects.filter(message_id__in=message_ids, device_id=new_device_id)
            .values_list("message_id", flat=True)
        )

        # 5) Source rows = user's existing encryptions for those messages (from any of user_device_ids),
        #    excluding messages that already have an entry for new_device_id
        #    We'll pick exactly one source per message_id.
        #    (Order by message_id then id to have deterministic first-row selection.)
        sources_qs = (
            MessageEncryption.objects
            .filter(message_id__in=message_ids, device_id__in=user_device_ids)
            .exclude(message_id__in=existing_for_new)
            .order_by("message_id", "id")
            .only("message_id", "encrypted_content")  # reduce DB payload
        )

        # 6) Build one row per message_id
        #    Use a dict to keep the first source per message_id
        src_by_msg = {}
        for src in sources_qs.iterator(chunk_size=2000):
            mid = src.message_id
            if mid not in src_by_msg:
                src_by_msg[mid] = src.encrypted_content

        if not src_by_msg:
            return Response({"backfilled": 0, "skipped": len(existing_for_new)}, status=status.HTTP_200_OK)

        # 7) Prepare bulk_create payload (only for messages missing new_device_id)
        to_create = []
        for mid, enc_content in src_by_msg.items():
            # Safety: if for any reason it already exists, skip (idempotent)
            if mid in existing_for_new:
                continue
            to_create.append(
                MessageEncryption(
                    message_id=mid,
                    device_id=new_device_id,
                    encrypted_content=enc_content,
                )
            )

        if not to_create:
            return Response({"backfilled": 0, "skipped": len(existing_for_new)}, status=status.HTTP_200_OK)

        # 8) Bulk create in batches
        target_mids = list(src_by_msg.keys())
        pre_count = MessageEncryption.objects.filter(
            message_id__in=target_mids, device_id=new_device_id
        ).count()

        batch_size = 1000
        with transaction.atomic():
            for i in range(0, len(to_create), batch_size):
                chunk = to_create[i:i+batch_size]
                MessageEncryption.objects.bulk_create(chunk, ignore_conflicts=True)

        post_count = MessageEncryption.objects.filter(
            message_id__in=target_mids, device_id=new_device_id
        ).count()

        created_count = max(0, post_count - pre_count)
        return Response({"backfilled": created_count, "skipped": len(existing_for_new)}, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="my-devices", permission_classes=[IsAuthenticated])
    def my_devices(self, request):
        user = request.user
        devices = UserDeviceKey.objects.filter(user=user).order_by('-last_used')
        serializer = UserDeviceKeySerializer(devices, many=True)
        return Response(serializer.data)
    
    # -------------------------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="send-device-deletion-code", permission_classes=[IsAuthenticated])
    def send_device_deletion_code(self, request):
        user = request.user
        device_id = request.data.get("device_id", "").strip().lower()


        if not device_id:
            return Response({"error": "Device ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = UserDeviceKey.objects.get(user=user, device_id=device_id)   
        except UserDeviceKey.DoesNotExist:
            return Response({"error": "Device not found."}, status=status.HTTP_404_NOT_FOUND)
        
        code = str(create_active_code(5))
        encrypted_code = cipher_suite.encrypt(code.encode()).decode()

        expiration_minutes = settings.EMAIL_CODE_EXPIRATION_MINUTES
        expiry = timezone.now() + datetime.timedelta(minutes=expiration_minutes)

        device.deletion_code = encrypted_code
        device.deletion_code_expiry = expiry
        device.save()

        context = {
            'activation_code': code,
            'user': user,
            'site_domain': settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "expiration_minutes": expiration_minutes,
            "current_year": timezone.now().year,
            "device_name": device.device_name,
            "device_ip": device.ip_address,
        }

        subject = "Confirm Device Deletion - TownLIT"
        success = send_custom_email(
            to=user.email,
            subject=subject,
            template_path='emails/account/confirm_device_deletion.html',
            context=context,
            text_template_path=None,
        )

        if not success:
            return Response({"error": "Failed to send confirmation code."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "A confirmation code was sent to your email."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="verify-delete-device", permission_classes=[IsAuthenticated])
    def verify_and_delete_device(self, request):
        user = request.user
        device_id = request.data.get("device_id", "").strip().lower()
        input_code = request.data.get("code")

        if not device_id or not input_code:
            return Response({"error": "Device ID and code are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = UserDeviceKey.objects.get(user=user, device_id=device_id)
        except UserDeviceKey.DoesNotExist:
            return Response({"error": "Device not found."}, status=status.HTTP_404_NOT_FOUND)

        if not device.deletion_code or not device.deletion_code_expiry:
            return Response({"error": "No code found. Please request again."}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > device.deletion_code_expiry:
            return Response({"error": "The code has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decrypted_code = cipher_suite.decrypt(device.deletion_code.encode()).decode()
        except Exception:
            return Response({"error": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)

        if decrypted_code != input_code:
            return Response({"error": "Incorrect verification code."}, status=status.HTTP_400_BAD_REQUEST)

        active_devices = UserDeviceKey.objects.filter(user=user, is_active=True)
        if active_devices.count() <= 1:
            return Response({"error": "Cannot delete your last active device."}, status=status.HTTP_400_BAD_REQUEST)

        device.delete()
        # device.deletion_code = None
        # device.deletion_code_expiry = None
        # device.save()

        return Response({"message": "Device deleted successfully."}, status=status.HTTP_200_OK)


