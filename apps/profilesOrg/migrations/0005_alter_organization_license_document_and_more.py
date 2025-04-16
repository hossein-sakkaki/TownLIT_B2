# Generated by Django 4.2.4 on 2025-03-25 02:48

import common.validators
from django.db import migrations, models
import utils


class Migration(migrations.Migration):

    dependencies = [
        ('profilesOrg', '0004_alter_organization_license_document_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='license_document',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_pdf_file, common.validators.validate_no_executable_file], verbose_name='License Document'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='logo',
            field=models.ImageField(default='media/sample/logo.png', upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Logo'),
        ),
    ]
