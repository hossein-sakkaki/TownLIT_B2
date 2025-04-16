from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.utils import timezone 


from apps.warehouse.models import WarehouseInventory
from apps.orders.models import Order
from apps.notifications.models import Notification
from apps.config.orders_constants import DELIVERY_AWAITING_HELP


from django.db.models.signals import pre_save, post_save, post_delete
from apps.orders.models import ShoppingCartItem
from apps.warehouse.models import TemporaryReservation



@receiver(post_save, sender=WarehouseInventory)
def check_inventory(sender, instance, **kwargs):
    if instance.quantity == 0:
        # Find orders with help requests related to this product
        related_orders = Order.objects.filter(
            shopping_cart__items__product=instance.product, 
            is_help_requested=True, 
            status=DELIVERY_AWAITING_HELP
        )
        # Loop through related orders and delete them
        for order in related_orders:
            Notification.objects.create(        # Need To More Edit نیاز به ویرایش در آینده
                user=order.user,
                message='The product you requested help for is now unavailable. Please consider selecting another product.',
                notification_type='product_unavailable',  
                created_at=timezone.now(),
                content_type=None,
                object_id=None,
                content_object=None,
                link=None  
            )
            order.delete()
            



# Signal to clean expired reservations when a ShoppingCartItem is saved --------------------------------
@receiver([post_save, pre_save], sender=ShoppingCartItem)
def clean_expired_reservations_on_save(sender, instance, **kwargs):
    """
    Signal to clean expired reservations before or after saving any shopping cart item.
    Covers adding or updating items in the cart.
    """
    clean_expired_reservations()

# Signal to clean expired reservations when a ShoppingCartItem is deleted
@receiver(post_delete, sender=ShoppingCartItem)
def clean_expired_reservations_on_delete(sender, instance, **kwargs):
    """
    Signal to clean expired reservations after deleting any shopping cart item.
    Covers removing items from the cart.
    """
    clean_expired_reservations()

@receiver([post_save, pre_save], sender=ShoppingCartItem)
def clean_expired_reservations(sender, instance, **kwargs):
    """
    Signal to clean expired reservations before saving any shopping cart item
    """
    now = timezone.now()
    expired_reservations = TemporaryReservation.objects.filter(expiry_date__lt=now)

    for reservation in expired_reservations:
        # Restore the product quantity to the warehouse inventory
        reservation.product.warehouse_inventory.quantity += reservation.reserved_quantity
        reservation.product.warehouse_inventory.save()

        # Delete the expired reservation
        reservation.delete()
