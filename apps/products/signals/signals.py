import os
from apps.products.models import Gallery, Product
from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver



@receiver(post_delete, sender=Product)
def delete_product_image(sender, instance, **kwargs):
    path = os.path.join(settings.MEDIA_ROOT, str(instance.image_name))
    if os.path.isfile(path):
        os.remove(path)

@receiver(post_delete, sender=Gallery)
def delete_gallery_image(sender, instance, **kwargs):
    path = os.path.join(settings.MEDIA_ROOT, str(instance.image_name))
    if os.path.isfile(path):
        os.remove(path)