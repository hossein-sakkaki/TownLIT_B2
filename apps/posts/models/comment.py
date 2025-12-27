from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from apps.posts.utils.content_router import resolve_content_path
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
    

# Comment Models ------------------------------------------------------------------------------------------------------------
class Comment(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_comments', verbose_name='Name')
    comment = encrypt(models.TextField(blank=True, null=True, verbose_name='Comment'))

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, db_index=True)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # parent (single-level reply)
    recomment = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True,
                                  related_name='responses', verbose_name='Recomment', db_index=True)

    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Time')
    is_active = models.BooleanField(default=True, null=True, blank=True)

    class Meta:
        verbose_name = "_Comment"
        verbose_name_plural = "_Comments"
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["recomment"]),
        ]

    def __str__(self):
        return f"Comment by {self.name.username}"

    @property
    def is_reply(self) -> bool:
        return self.recomment_id is not None

    # ==========================================================
    # Absolute URL for frontend deep-linking (Comments)
    # ==========================================================
    def get_absolute_url(self) -> str:
        """
        Deep-link to parent content via content_router. 
        Supports both root comments and replies.
        """
        try:
            model_name = self.content_type.model
            content_obj = self.content_object
            slug = getattr(content_obj, "slug", None)
            subtype = getattr(content_obj, "type", None)

            if not slug:
                return "#"

            # --- Detect focus type ---
            if self.recomment_id:
                focus_param = f"reply-{self.pk}:parent-{self.recomment_id}"
            else:
                focus_param = f"comment-{self.pk}"

            # --- Generate final path ---
            return resolve_content_path(
                model_name=model_name,
                slug=slug,
                subtype=subtype,
                focus=focus_param,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Comment.get_absolute_url] failed: {e}")
            return "#"
