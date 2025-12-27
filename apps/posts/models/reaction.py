from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from apps.posts.constants import REACTION_TYPE_CHOICES
from apps.posts.utils.content_router import resolve_content_path
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


    
# Reaction Models ---------------------------------------------------------------------------------
class Reaction(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='user_reactions',
        verbose_name='Name'
    )
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_TYPE_CHOICES,
        verbose_name='Reaction Type'
    )
    message = encrypt(models.TextField(blank=True, null=True, verbose_name='Reaction Message'))

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Timestamp')

    def __str__(self):
        return f'{self.name.username} reacted with {self.reaction_type}'

    class Meta:
        verbose_name = "_Reaction"
        verbose_name_plural = "_Reactions"
        unique_together = ('name', 'reaction_type', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['name', 'content_type', 'object_id']),
        ]

    # ==========================================================
    # Absolute URL for frontend deep-linking (Reactions)
    # ==========================================================
    def get_absolute_url(self) -> str:
        """
        Deep-link to parent content via content_router.
        Adds ?focus=reaction-<id> for frontend highlight.
        """
        try:
            model_name = self.content_type.model
            slug = getattr(self.content_object, "slug", None)
            subtype = getattr(self.content_object, "type", None)  # optional: "video", "written", etc.

            if slug:
                return resolve_content_path(
                    model_name,
                    slug,
                    subtype,
                    focus=f"reaction-{self.pk}"
                )
        except Exception:
            pass
        return "#"
