# apps/accounts/models/devices.py

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
from django.utils import timezone

cipher_suite = Fernet(settings.FERNET_KEY)


class UserDeviceKey(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_keys')
    device_id = models.CharField(max_length=100, verbose_name="Device ID")
    public_key = models.TextField(verbose_name="Public Key (PEM)")
    device_name = models.CharField(max_length=255, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    platform = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="web / android / ios (for future multi-platform support)",
    )
    push_token = models.CharField(
        max_length=512,
        blank=True,
        null=True,
        help_text="Universal push registration token (FCM/WebPush/APNs)",
    )

    install_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    fp_hint = models.CharField(max_length=128, blank=True, null=True, db_index=True)

    location_city = models.CharField(max_length=100, blank=True, null=True)
    location_region = models.CharField(max_length=100, blank=True, null=True)
    location_country = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=100, blank=True, null=True)
    organization = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    deletion_code = models.CharField(max_length=255, blank=True, null=True)
    deletion_code_expiry = models.DateTimeField(blank=True, null=True)

    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)

    pop_challenge_hash = models.BinaryField(blank=True, null=True)
    pop_challenge_expiry = models.DateTimeField(blank=True, null=True)
    pop_attempts = models.IntegerField(default=0)

    def is_delete_code_valid(self, code: str) -> bool:
        if not self.deletion_code or not self.deletion_code_expiry:
            return False
        if timezone.now() > self.deletion_code_expiry:
            return False

        try:
            decrypted = cipher_suite.decrypt(self.deletion_code.encode()).decode()
            return decrypted == code
        except Exception:
            return False

    class Meta:
        unique_together = ('user', 'device_id')

    def __str__(self):
        return f"{self.user} - {self.device_name or self.device_id}"


class UserDeviceKeyBackup(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_key_backups')
    device_id = models.CharField(max_length=100, db_index=True)
    blob = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'device_id')

    def __str__(self):
        return f"KeyBackup(user={self.user_id}, device={self.device_id})"


class UserSecurityProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sec_profile")
    has_passphrase = models.BooleanField(default=False)
    kdf = models.CharField(max_length=20, default="PBKDF2")
    iterations = models.IntegerField(default=600000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"UserSecurityProfile(user={self.user_id}, has_pp={self.has_passphrase})"