# Generated by Django 4.2.4 on 2025-03-25 02:54

import common.validators
from django.db import migrations, models
import utils


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_alter_customuser_image_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='image_name',
            field=models.ImageField(blank=True, default='media/sample/user.png', null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Image'),
        ),
    ]
