# Generated by Django 4.2.4 on 2025-03-25 02:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('store', '0001_initial'),
        ('orders', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='store.store', verbose_name='Store'),
        ),
        migrations.AddField(
            model_name='deliveryinformation',
            name='order',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_info', to='orders.order', verbose_name='Order'),
        ),
    ]
