# Generated by Django 4.2.4 on 2025-06-06 22:37

from django.db import migrations, models
import utils.common.utils
import validators.mediaValidators.audio_validators
import validators.mediaValidators.image_validators
import validators.mediaValidators.pdf_validators
import validators.mediaValidators.video_validators
import validators.security_validators


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0003_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='announcement',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Announcement Image'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.audio_validators.validate_audio_file, validators.security_validators.validate_no_executable_file], verbose_name='Audio Lesson'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Image Lesson'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.video_validators.validate_video_file, validators.security_validators.validate_no_executable_file], verbose_name='Video Lesson'),
        ),
        migrations.AlterField(
            model_name='library',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Book Image'),
        ),
        migrations.AlterField(
            model_name='library',
            name='license_document',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.pdf_validators.validate_pdf_file, validators.security_validators.validate_no_executable_file], verbose_name='License Document'),
        ),
        migrations.AlterField(
            model_name='library',
            name='pdf_file',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.pdf_validators.validate_pdf_file, validators.security_validators.validate_no_executable_file], verbose_name='Book File'),
        ),
        migrations.AlterField(
            model_name='mediacontent',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.pdf_validators.validate_pdf_file, validators.security_validators.validate_no_executable_file], verbose_name='Media File'),
        ),
        migrations.AlterField(
            model_name='mission',
            name='image_or_video',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file, validators.security_validators.validate_no_executable_file], verbose_name='Mission Image/Video'),
        ),
        migrations.AlterField(
            model_name='moment',
            name='moment_file',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.pdf_validators.validate_pdf_file, validators.security_validators.validate_no_executable_file], verbose_name='Image/Video'),
        ),
        migrations.AlterField(
            model_name='pray',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Pray Image'),
        ),
        migrations.AlterField(
            model_name='preach',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Lesson Image'),
        ),
        migrations.AlterField(
            model_name='preach',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.video_validators.validate_video_file, validators.security_validators.validate_no_executable_file], verbose_name='Lesson Video'),
        ),
        migrations.AlterField(
            model_name='serviceevent',
            name='event_banner',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Event Banner'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.audio_validators.validate_audio_file, validators.security_validators.validate_no_executable_file], verbose_name='Testimony Audio'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='thumbnail_1',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Thumbnail 1'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='thumbnail_2',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Thumbnail 2'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.video_validators.validate_video_file, validators.security_validators.validate_no_executable_file], verbose_name='Testimony Video'),
        ),
        migrations.AlterField(
            model_name='worship',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.audio_validators.validate_audio_file, validators.security_validators.validate_no_executable_file], verbose_name='Worship Audio'),
        ),
        migrations.AlterField(
            model_name='worship',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Worship Image'),
        ),
        migrations.AlterField(
            model_name='worship',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.video_validators.validate_video_file, validators.security_validators.validate_no_executable_file], verbose_name='Worship Video'),
        ),
    ]
