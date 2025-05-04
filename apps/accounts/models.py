from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from datetime import timedelta
from django.utils.text import slugify
from colorfield.fields import ColorField
import bcrypt
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings

from apps.config.organization_constants import LANGUAGE_CHOICES, ENGLISH, COUNTRY_CHOICES
from apps.config.accounts_constants import SOCIAL_MEDIA_CHOICES
from apps.config.constants import (
                                USER_LABEL_CHOICES,
                                ORGANIZATION_SERVICE_CATEGORY_CHOICES, 
                                SPIRITUAL_MINISTRY_CHOICES,
                                GENDER_CHOICES,
                                ADDRESS_TYPE_CHOICES, HOME
                            )
from common.validators import (
                                validate_image_or_video_file,
                                validate_no_executable_file,
                                validate_phone_number
                            )

from utils.common.utils import FileUpload, create_active_code


# USER & SUPERUSER Manager ------------------------------------------
class CustomUserManager(BaseUserManager):

    def create_user(self,
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
                    password=None
                ):
        
        # Ensure email is provided
        if not email:
            raise ValueError('Email is required')

        # Handle optional fields with default values
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

        # Create user instance
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
        )
        
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self,
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
                        user_active_code=None,
                        user_active_code_expiry=None,
                        reset_token=None,
                        reset_token_expiration=None,
                        password=None
                    ):
        
        # Create a regular user
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
        
        # Set additional attributes for superuser
        user.is_active = True
        user.is_admin = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# ADDRESS Manager ---------------------------------------------
class Address(models.Model):
    id = models.BigAutoField(primary_key=True)
    street_number = models.CharField(max_length=100, blank=True, verbose_name='Streen Number')
    route = models.CharField(max_length=100, blank=True, verbose_name='Route')
    locality = models.CharField(max_length=100, blank=True, verbose_name='Locality')
    administrative_area_level_1 = models.CharField(max_length=100, blank=True, verbose_name='Administrative Area Level 1')
    postal_code = models.CharField(max_length=20, blank=True, verbose_name='Postal Code')
    country = models.CharField(max_length=100, blank=True, verbose_name='Country')
    additional = models.CharField(max_length=400, null=True, blank=True, verbose_name='Additional')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default=HOME, verbose_name='Address Type')

    def __str__(self):
        address_parts = [self.street_number, self.route, self.locality, self.administrative_area_level_1, self.postal_code, self.country]
        if self.additional:
            address_parts.append(self.additional)
        return ', '.join(address_parts)

    class Meta:
        verbose_name = "Custom Address"
        verbose_name_plural = "Custom Addresses"

# LABEL Manager -----------------------------------------------------
class CustomLabel(models.Model):
    name = models.CharField(max_length=20, choices=USER_LABEL_CHOICES, unique=True, verbose_name='Label Name')
    color = ColorField(verbose_name='Color Code')
    description = models.CharField(max_length=500, null=True, blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    
    class Meta:
        verbose_name = "Label"
        verbose_name_plural = "Labels"

    def __str__(self):
        return self.name

# URL Manager ---------------------------------------------------
class SocialMediaType(models.Model):
    name = models.CharField(max_length=20, choices=SOCIAL_MEDIA_CHOICES, unique=True, verbose_name='Social Media Name')
    icon_class = models.CharField(max_length=100, null=True, blank=True, verbose_name='FontAwesome Class')
    icon_svg = models.TextField(null=True, blank=True, verbose_name='SVG Icon Code')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = 'Social Media Type'
        verbose_name_plural = 'Social Media Types'
    
    def __str__(self):
        return self.name
    
class SocialMediaLink(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_media_type = models.ForeignKey(SocialMediaType, on_delete=models.PROTECT, related_name='url_links', verbose_name='Social Media Type')
    link = models.URLField(max_length=500, verbose_name='URL Link')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="Content Type")
    object_id = models.PositiveIntegerField(verbose_name="Object ID")
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = "URL Link"
        verbose_name_plural = "URL Links"

    def __str__(self):
        return self.link

# ORGANIZATION SERVICE CATEGORY Manager ---------------------------------------------------------
class OrganizationService(models.Model):
    name = models.CharField(max_length=50, choices=ORGANIZATION_SERVICE_CATEGORY_CHOICES, unique=True, verbose_name='Organization Service')
    description = models.CharField(max_length=500, null=True, blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = "Organization Service Category"
        verbose_name_plural = "Organization Service Categories"

    def __str__(self):
        return self.name

    
# MEMBER SERVICE TYPE Manager -------------------------------------------------------------
class SpiritualService(models.Model):
    name = models.CharField(max_length=40, choices=SPIRITUAL_MINISTRY_CHOICES, unique=True, verbose_name='Name of Service')
    color = ColorField(null=True, blank=True, verbose_name='Color Code')
    description = models.CharField(max_length=300, null=True, blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = "Spiritual Service"
        verbose_name_plural = "Spiritual Services" 
        
    def __str__(self):
        return self.name
    
# CUSTOMUSER Manager ----------------------------------------------
class CustomUser(AbstractBaseUser, PermissionsMixin):
    IMAGE = FileUpload('accounts', 'photos', 'custom_user')
    
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=254, unique=True, verbose_name='Email')
    last_email_change = models.DateTimeField(null=True, blank=True, verbose_name='Last Email Change')
    email_change_tokens = models.JSONField(null=True, blank=True, verbose_name='Email Change Tokens', help_text='Stores tokens for email change verification.')

    def change_email(self, new_email):
        self.email = new_email
        self.last_email_change = timezone.now()
        self.save()
        
    mobile_number = models.CharField(max_length=20, unique=False, null=True, blank=True, validators=[validate_phone_number], verbose_name='Mobile Number')
    mobile_verification_code = models.CharField(max_length=200, null=True, blank=True, verbose_name="Mobile Verification Code")
    mobile_verification_expiry = models.DateTimeField(null=True, blank=True)
    
    name = models.CharField(max_length=40, null=True, blank=True, verbose_name='Name')
    family = models.CharField(max_length=40, null=True, blank=True, verbose_name='Family')
    username = models.CharField(max_length=40, unique=True, blank=True, verbose_name='Username')
    def save(self, *args, **kwargs):
        if not self.username:
            base_username = slugify(self.name + '_' + self.family)
            suggested_username = base_username
            counter = 1
            while CustomUser.objects.filter(username=suggested_username).exists():
                suggested_username = f"{base_username}_{counter}"
                counter += 1
            self.username = suggested_username
        super().save(*args, **kwargs)
        
    birthday = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True, verbose_name='Birthday')        
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, null=True, blank=True, verbose_name='Gender')
    label = models.ForeignKey(CustomLabel, on_delete=models.CASCADE, null=True, blank=True, related_name='user_label', verbose_name="User Label")

    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=True, null=True, verbose_name="Country")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="City")
    primary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default=ENGLISH, verbose_name='Primary Language')
    secondary_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, null=True, blank=True, verbose_name='Secondary Language')
    
    image_name = models.ImageField(upload_to=IMAGE.dir_upload, default='media/sample/user.png', null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Image')
    user_active_code = models.CharField(max_length=200, null=True, blank=True)
    user_active_code_expiry = models.DateTimeField(null=True, blank=True)
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')
    
    deletion_requested_at = models.DateTimeField(null=True, blank=True, verbose_name='Deletion Requested At')
    is_deleted = models.BooleanField(default=False, verbose_name="Is Deleted")
    reactivated_at = models.DateTimeField(null=True, blank=True, verbose_name='Reactivated Date')

    reset_token = models.CharField(max_length=255, null=True, blank=True) # For Forgot Password
    reset_token_expiration = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=False, verbose_name='Is Active')
    is_admin = models.BooleanField(default=False, verbose_name='Is Admin')
    is_member = models.BooleanField(default=False, verbose_name='Is Member')

    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    # Push Notification for Android and IOS
    registration_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="FCM Registration ID") 
    
    # 2FA Protocol ------------------------------------------------------------
    two_factor_enabled = models.BooleanField(default=False, verbose_name="Two-Factor Authentication Enabled")
    two_factor_token = models.CharField(max_length=60, null=True, blank=True, verbose_name="Two-Factor Token")
    two_factor_token_expiry = models.DateTimeField(null=True, blank=True, verbose_name="Two-Factor Token Expiry")
    
    def generate_two_factor_token(self):
        token = str(create_active_code(6))
        hashed_token = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
        self.two_factor_token = hashed_token.decode('utf-8')
        self.two_factor_token_expiry = timezone.now() + timedelta(minutes=15)
        self.save()
        return token

    # Method to validate the entered OTP by comparing it with the stored hash
    def validate_two_factor_token(self, entered_token):
        if self.two_factor_token_expiry < timezone.now():
            return False
        return bcrypt.checkpw(entered_token.encode('utf-8'), self.two_factor_token.encode('utf-8'))

    # Access and Delete pin ----------------------------------------------------
    pin_security_enabled = models.BooleanField(default=False, verbose_name="Pin Security Status")
    access_pin = models.CharField(max_length=255, blank=True, null=True, verbose_name="Access Pin")
    delete_pin = models.CharField(max_length=255, blank=True, null=True, verbose_name="Delete Pin")

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
    
    # Privacy
    show_email = models.BooleanField(default=False, verbose_name="Show Email Publicly")
    show_phone_number = models.BooleanField(default=False, verbose_name="Show Phone Number Publicly")
    show_country = models.BooleanField(default=False, verbose_name="Show Country Publicly")
    show_city = models.BooleanField(default=False, verbose_name="Show City Publicly")
    
    is_account_paused = models.BooleanField(default=False, verbose_name='Is Account Paused')
    
    
    def has_device_key(self, device_id: str) -> bool:
        return self.device_keys.filter(device_id=device_id, is_active=True).exists()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()
        
    class Meta:
        verbose_name = "1. Custom User"
        verbose_name_plural = "1. Custom Users"
        
    def is_member_user(self):
        return self.is_member
    
    @property
    def is_staff(self):
        return self.is_admin
    
    def __str__(self):
        return f'{self.username}'
    
    def get_absolute_url(self):
        return f"/{self.username}"
    

# User Device Key Model -----------------------------------------------------
class UserDeviceKey(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_keys')
    device_id = models.CharField(max_length=100, verbose_name="Device ID")  # از کلاینت میاد
    public_key = models.TextField(verbose_name="Public Key (PEM)")
    device_name = models.CharField(max_length=255, blank=True, null=True)  # مثلا "iPhone 14"
    user_agent = models.TextField(blank=True, null=True)  # از request.META گرفته میشه
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'device_id')


# Invite Code Model -----------------------------------------------------
class InviteCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    email = models.EmailField(null=True, blank=True, help_text="Optional: restrict to specific email")
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    is_used = models.BooleanField(default=False)
    
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='used_invite_code'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    invite_email_sent = models.BooleanField(default=False)
    invite_email_sent_at = models.DateTimeField(null=True, blank=True)
    
    def mark_as_used(self, user):
        self.is_used = True
        self.used_by = user
        self.used_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.code} ({'USED' if self.is_used else 'UNUSED'})"