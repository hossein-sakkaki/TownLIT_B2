# apps/accounts/models/user.py
from datetime import timedelta

import bcrypt
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.accounts.utils.username import generate_unique_username_from_email
from apps.accounts.utils.name_normalizer import normalize_person_name

from apps.accounts.constants.gender import GENDER_CHOICES
from apps.profilesOrg.constants import LANGUAGE_CHOICES, ENGLISH, COUNTRY_CHOICES

from validators.user_validators import validate_phone_number
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file

from utils.common.utils import FileUpload, create_active_code


class CustomUserManager(BaseUserManager):

    def create_user(
        self,
        email,
        mobile_number=None,
        name=None,
        family=None,
        username=None,
        birthday=None,
        gender=None,
        country=None,
        city=None,
        primary_language=None,
        secondary_language=None,
        image_name=None,
        avatar_version=None,
        user_active_code=None,
        user_active_code_expiry=None,
        reset_token=None,
        reset_token_expiration=None,
        is_member=False,
        is_suspended=False,
        reports_count=0,
        two_factor_enabled=False,
        registration_id=None,
        pin_security_enabled=False,
        access_pin=None,
        delete_pin=None,
        show_email=False,
        show_phone_number=False,
        show_country=False,
        show_city=False,
        is_account_paused=False,
        password=None,
    ):
        if not email:
            raise ValueError('Email is required')

        mobile_number = mobile_number if mobile_number else ''
        name = name if name else ''
        family = family if family else ''
        username = username if username else ''
        birthday = birthday if birthday else None
        gender = gender if gender else None
        image_name = image_name if image_name else None

        primary_language = primary_language or 'en'
        secondary_language = secondary_language or None
        country = country or None
        city = city or None

        registration_id = registration_id or None
        delete_pin = delete_pin or None
        access_pin = access_pin or None
        user_active_code = user_active_code if user_active_code else None
        user_active_code_expiry = user_active_code_expiry or None
        reset_token = reset_token if reset_token else None
        reset_token_expiration = reset_token_expiration if reset_token_expiration else None
        registration_started_at = timezone.now()

        user = self.model(
            email=self.normalize_email(email),
            mobile_number=mobile_number,
            name=name,
            family=family,
            username=username,
            birthday=birthday,
            gender=gender,
            country=country,
            city=city,
            primary_language=primary_language,
            secondary_language=secondary_language,
            image_name=image_name,
            user_active_code=user_active_code,
            user_active_code_expiry=user_active_code_expiry,
            reset_token=reset_token,
            reset_token_expiration=reset_token_expiration,
            is_member=is_member,
            is_suspended=is_suspended,
            reports_count=reports_count,
            two_factor_enabled=two_factor_enabled,
            registration_id=registration_id,
            pin_security_enabled=pin_security_enabled,
            access_pin=access_pin,
            delete_pin=delete_pin,
            show_email=show_email,
            show_phone_number=show_phone_number,
            show_country=show_country,
            show_city=show_city,
            is_account_paused=is_account_paused,
            registration_started_at=registration_started_at,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email,
        mobile_number=None,
        name=None,
        family=None,
        username=None,
        birthday=None,
        gender=None,
        country=None,
        city=None,
        primary_language=None,
        secondary_language=None,
        image_name=None,
        avatar_version=None,
        user_active_code=None,
        user_active_code_expiry=None,
        reset_token=None,
        reset_token_expiration=None,
        password=None,
    ):
        user = self.create_user(
            email=email,
            mobile_number=mobile_number,
            name=name,
            family=family,
            username=username,
            birthday=birthday,
            gender=gender,
            country=country,
            city=city,
            primary_language=primary_language,
            secondary_language=secondary_language,
            image_name=image_name,
            user_active_code=user_active_code,
            user_active_code_expiry=user_active_code_expiry,
            reset_token=reset_token,
            reset_token_expiration=reset_token_expiration,
            password=password,
            is_member=True,
        )

        user.is_active = True
        user.is_admin = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    IMAGE = FileUpload('accounts', 'photos', 'custom_user')

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=254, unique=True, verbose_name='Email')
    last_email_change = models.DateTimeField(null=True, blank=True, verbose_name='Last Email Change')
    email_change_tokens = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Email Change Tokens',
        help_text='Stores tokens for email change verification.',
    )

    def change_email(self, new_email):
        self.email = new_email
        self.last_email_change = timezone.now()
        self.save()

    mobile_number = models.CharField(
        max_length=20,
        unique=False,
        null=True,
        blank=True,
        validators=[validate_phone_number],
        verbose_name='Mobile Number',
    )
    mobile_verification_code = models.CharField(max_length=200, null=True, blank=True, verbose_name="Mobile Verification Code")
    mobile_verification_expiry = models.DateTimeField(null=True, blank=True)

    name = models.CharField(max_length=40, null=True, blank=True, verbose_name='Name')
    family = models.CharField(max_length=40, null=True, blank=True, verbose_name='Family')
    username = models.CharField(max_length=40, unique=True, blank=True, verbose_name='Username')

    birthday = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True, verbose_name='Birthday')
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, null=True, blank=True, verbose_name='Gender')
    label = models.ForeignKey(
        "accounts.CustomLabel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_label',
        verbose_name="User Label",
    )

    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=True, null=True, verbose_name="Country")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="City")
    primary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, null=True, blank=True, verbose_name='Primary Language')
    secondary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, null=True, blank=True, verbose_name='Secondary Language')

    image_name = models.ImageField(
        upload_to=IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name='Image',
    )
    avatar_version = models.PositiveIntegerField(default=1)
    user_active_code = models.CharField(max_length=200, null=True, blank=True)
    user_active_code_expiry = models.DateTimeField(null=True, blank=True)
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')

    deletion_requested_at = models.DateTimeField(null=True, blank=True, verbose_name='Deletion Requested At')
    is_deleted = models.BooleanField(default=False, verbose_name="Is Deleted")
    reactivated_at = models.DateTimeField(null=True, blank=True, verbose_name='Reactivated Date')

    reset_token = models.CharField(max_length=255, null=True, blank=True)
    reset_token_expiration = models.DateTimeField(null=True, blank=True)

    registration_started_at = models.DateTimeField(default=timezone.now, verbose_name='Registration Start Date')
    is_active = models.BooleanField(default=False, verbose_name='Is Active')
    is_admin = models.BooleanField(default=False, verbose_name='Is Admin')
    is_member = models.BooleanField(default=False, verbose_name='Is Member')

    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")

    registration_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="FCM Registration ID")

    two_factor_enabled = models.BooleanField(default=False, verbose_name="Two-Factor Authentication Enabled")
    two_factor_token = models.CharField(max_length=60, null=True, blank=True, verbose_name="Two-Factor Token")
    two_factor_token_expiry = models.DateTimeField(null=True, blank=True, verbose_name="Two-Factor Token Expiry")

    pin_security_enabled = models.BooleanField(default=False, verbose_name="Pin Security Status")
    access_pin = models.CharField(max_length=255, blank=True, null=True, verbose_name="Access Pin")
    delete_pin = models.CharField(max_length=255, blank=True, null=True, verbose_name="Delete Pin")

    show_email = models.BooleanField(default=False, verbose_name="Show Email Publicly")
    show_phone_number = models.BooleanField(default=False, verbose_name="Show Phone Number Publicly")
    show_country = models.BooleanField(default=False, verbose_name="Show Country Publicly")
    show_city = models.BooleanField(default=False, verbose_name="Show City Publicly")

    is_account_paused = models.BooleanField(default=False, verbose_name='Is Account Paused')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    class Meta:
        verbose_name = "1. Custom User"
        verbose_name_plural = "1. Custom Users"

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = normalize_person_name(self.name)

        if self.family is not None:
            self.family = normalize_person_name(self.family)

        if not self.username:
            self.username = generate_unique_username_from_email(
                email=self.email,
                model_cls=CustomUser,
            )

        super().save(*args, **kwargs)

    def generate_two_factor_token(self):
        token = str(create_active_code(6))
        hashed_token = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
        self.two_factor_token = hashed_token.decode('utf-8')
        self.two_factor_token_expiry = timezone.now() + timedelta(minutes=settings.EMAIL_CODE_EXPIRATION_MINUTES)
        self.save()
        return token

    def validate_two_factor_token(self, entered_token):
        if not self.two_factor_token or not self.two_factor_token_expiry:
            return "no_token"
        if self.two_factor_token_expiry < timezone.now():
            return "expired"
        if bcrypt.checkpw(entered_token.encode('utf-8'), self.two_factor_token.encode('utf-8')):
            return "valid"
        return "invalid"

    def set_access_pin(self, pin: str):
        salt = bcrypt.gensalt()
        hashed_pin = bcrypt.hashpw(pin.encode('utf-8'), salt)
        self.access_pin = hashed_pin.decode('utf-8')

    def set_delete_pin(self, pin: str):
        salt = bcrypt.gensalt()
        hashed_pin = bcrypt.hashpw(pin.encode('utf-8'), salt)
        self.delete_pin = hashed_pin.decode('utf-8')

    def verify_access_pin(self, entered_pin: str) -> bool:
        if not self.access_pin:
            return False
        return bcrypt.checkpw(entered_pin.encode('utf-8'), self.access_pin.encode('utf-8'))

    def verify_delete_pin(self, entered_pin: str) -> bool:
        if not self.delete_pin:
            return False
        return bcrypt.checkpw(entered_pin.encode('utf-8'), self.delete_pin.encode('utf-8'))

    def has_device_key(self, device_id: str) -> bool:
        return self.device_keys.filter(device_id=device_id, is_active=True).exists()

    def is_member_user(self):
        return self.is_member

    @property
    def is_verified_identity(self) -> bool:
        iv = getattr(self, "identity_verification", None)
        grant = self.identity_grants.filter(is_active=True).first()
        return bool((iv and iv.status == "verified") or grant)

    @property
    def identity_level(self) -> str:
        iv = getattr(self, "identity_verification", None)
        return getattr(iv, "level", None) or "basic"

    @property
    def trust_score_value(self):
        trust = getattr(self, "trust_score", None)
        return trust.score if trust else 0

    @property
    def is_verification_eligible(self):
        trust = getattr(self, "trust_score", None)

        if not trust:
            return False

        if self.is_verified_identity:
            return False

        return bool(trust.eligible_for_verification)

    @property
    def has_litshield(self) -> bool:
        grant = getattr(self, "litshield_grant", None)
        return bool(grant and grant.is_active)

    @property
    def image_url(self):
        if self.image_name:
            return self.image_name.url
        return settings.DEFAULT_USER_AVATAR_URL

    @property
    def is_staff(self):
        return self.is_admin

    def __str__(self):
        return f'{self.username}'

    def get_absolute_url(self):
        return f"/{self.username}"