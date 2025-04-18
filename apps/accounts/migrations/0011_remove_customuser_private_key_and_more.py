# Generated by Django 4.2.4 on 2025-04-07 16:54

import common.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import utils


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_alter_customuser_image_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customuser',
            name='private_key',
        ),
        migrations.RemoveField(
            model_name='customuser',
            name='private_key_is_encrypted',
        ),
        migrations.RemoveField(
            model_name='customuser',
            name='public_key',
        ),
        migrations.AlterField(
            model_name='customuser',
            name='image_name',
            field=models.ImageField(blank=True, default='media/sample/user.png', null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Image'),
        ),
        migrations.CreateModel(
            name='UserDeviceKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_id', models.CharField(max_length=100, verbose_name='Device ID')),
                ('public_key', models.TextField(verbose_name='Public Key (PEM)')),
                ('device_name', models.CharField(blank=True, max_length=255, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'device_id')},
            },
        ),
    ]
