# Generated by Django 4.2.4 on 2025-03-25 02:14

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveryInformation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('carrier', models.CharField(max_length=100, verbose_name='Delivery Carrier')),
                ('tracking_number', models.CharField(blank=True, max_length=100, null=True, verbose_name='Tracking Number')),
                ('estimated_delivery_date', models.DateTimeField(blank=True, null=True, verbose_name='Estimated Delivery Date')),
                ('actual_delivery_date', models.DateTimeField(blank=True, null=True, verbose_name='Actual Delivery Date')),
                ('carrier_contact_number', models.CharField(blank=True, max_length=20, null=True, verbose_name='Carrier Contact Number')),
                ('status', models.CharField(choices=[('awaiting_help', 'Awaiting Help'), ('in_payment', 'In Payment'), ('in_transit', 'In Transit'), ('delivered', 'Delivered'), ('paid', 'Paid'), ('cancelled', 'Cancelled')], default='in_payment', max_length=20, verbose_name='Delivery Status')),
                ('tracking_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='Tracking URL')),
            ],
            options={
                'verbose_name': 'Delivery Information',
                'verbose_name_plural': 'Delivery Information',
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Order Date')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('returned', 'Returned')], default='pending', max_length=20, verbose_name='Order Status')),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Total Price')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Order Notes')),
                ('is_help_requested', models.BooleanField(default=False, verbose_name='Help Requested')),
                ('help_message', models.TextField(blank=True, null=True, verbose_name='Help Message')),
            ],
            options={
                'verbose_name': 'Order',
                'verbose_name_plural': 'Orders',
                'ordering': ['-order_date'],
            },
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('price_at_purchase', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Price at Purchase')),
            ],
            options={
                'verbose_name': 'Order Item',
                'verbose_name_plural': 'Order Items',
            },
        ),
        migrations.CreateModel(
            name='OrderStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('returned', 'Returned')], max_length=20, verbose_name='Order Status')),
                ('change_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Change Date')),
            ],
            options={
                'verbose_name': 'Order Status History',
                'verbose_name_plural': 'Order Status Histories',
                'ordering': ['-change_date'],
            },
        ),
        migrations.CreateModel(
            name='ReturnRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Request Date')),
                ('reason', models.TextField(verbose_name='Reason for Return')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20, verbose_name='Request Status')),
            ],
            options={
                'verbose_name': 'Return Request',
                'verbose_name_plural': 'Return Requests',
                'ordering': ['-request_date'],
            },
        ),
        migrations.CreateModel(
            name='ShoppingCart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
            ],
            options={
                'verbose_name': 'Shopping Cart',
                'verbose_name_plural': 'Shopping Carts',
            },
        ),
        migrations.CreateModel(
            name='ShoppingCartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='orders.shoppingcart', verbose_name='Shopping Cart')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shopping_cart_items', to='products.product', verbose_name='Product')),
            ],
            options={
                'verbose_name': 'Shopping Cart Item',
                'verbose_name_plural': 'Shopping Cart Items',
            },
        ),
    ]
