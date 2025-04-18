# Generated by Django 4.2.4 on 2025-03-25 02:28

import common.validators
from django.db import migrations, models
import utils


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_alter_store_store_license_alter_store_store_logo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='store',
            name='store_license',
            field=models.FileField(upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_pdf_file, common.validators.validate_no_executable_file], verbose_name='Store License'),
        ),
        migrations.AlterField(
            model_name='store',
            name='store_logo',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Store Logo'),
        ),
    ]
