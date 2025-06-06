# Generated by Django 4.2.4 on 2025-06-06 22:37

import ckeditor_uploader.fields
from django.db import migrations, models
import utils.common.utils
import validators.mediaValidators.image_validators
import validators.mediaValidators.video_validators
import validators.security_validators


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='officialvideo',
            name='description',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='officialvideo',
            name='thumbnail',
            field=models.FileField(upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Thumbnail / Poster'),
        ),
        migrations.AlterField(
            model_name='officialvideo',
            name='video_file',
            field=models.FileField(upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.video_validators.validate_video_file, validators.security_validators.validate_no_executable_file], verbose_name='Video File'),
        ),
        migrations.AlterField(
            model_name='termsandpolicy',
            name='policy_type',
            field=models.CharField(choices=[('privacy_policy', 'Privacy Policy'), ('cookie_policy', 'Cookie Policy'), ('terms_of_service', 'Terms of Service'), ('copyright_policy', 'Copyright Policy'), ('community_guidelines', 'Community Guidelines'), ('vision_and_mission', 'Vision and Mission'), ('townlit_history', 'TownLIT History'), ('townlit_beliefs', 'TownLIT Beliefs')], max_length=50, verbose_name='Policy Type'),
        ),
        migrations.AlterField(
            model_name='userfeedback',
            name='screenshot',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Document'),
        ),
    ]
