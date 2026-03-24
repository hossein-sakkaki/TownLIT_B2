# apps/profiles/models/client.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from utils.common.utils import FileUpload, SlugMixin
from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.security_validators import validate_no_executable_file

CustomUser = get_user_model()


class ClientRequest(models.Model):
    DOCUMENT = FileUpload("profiles", "documents", "client_request")

    id = models.BigAutoField(primary_key=True)
    request = models.CharField(max_length=50, verbose_name="Request")
    description = models.CharField(max_length=500, verbose_name="Description")
    document_1 = models.FileField(
        upload_to=DOCUMENT,
        null=True,
        blank=True,
        validators=[validate_pdf_file, validate_no_executable_file],
        verbose_name="Document 1",
    )
    document_2 = models.FileField(
        upload_to=DOCUMENT,
        null=True,
        blank=True,
        validators=[validate_pdf_file, validate_no_executable_file],
        verbose_name="Document 2",
    )

    register_date = models.DateField(default=timezone.now, verbose_name="Register Date")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        verbose_name = "Client Request"
        verbose_name_plural = "Client Requests"

    def __str__(self):
        return self.request


class Client(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="client_profile",
        verbose_name="User",
    )
    organization_clients = models.ManyToManyField(
        "profilesOrg.Organization",
        blank=True,
        related_name="organization_clients",
        verbose_name="Organization Clients",
    )
    request = models.ForeignKey(
        ClientRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Request",
    )
    register_date = models.DateField(default=timezone.now, verbose_name="Register Date")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    url_name = "client_detail"

    class Meta:
        verbose_name = "4. Client"
        verbose_name_plural = "4. Clients"

    def __str__(self):
        return self.user.username

    def get_slug_source(self):
        return self.user.username