# Generated by Django 4.2.4 on 2025-03-25 03:00

import common.validators
from django.db import migrations, models
import utils


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0009_alter_announcement_image_alter_lesson_audio_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='announcement',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file], verbose_name='Announcement Image'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_audio_file, common.validators.validate_no_executable_file], verbose_name='Audio Lesson'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file], verbose_name='Image Lesson'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Video Lesson'),
        ),
        migrations.AlterField(
            model_name='library',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Book Image'),
        ),
        migrations.AlterField(
            model_name='library',
            name='license_document',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_pdf_file, common.validators.validate_no_executable_file], verbose_name='License Document'),
        ),
        migrations.AlterField(
            model_name='library',
            name='pdf_file',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_pdf_file, common.validators.validate_no_executable_file], verbose_name='Book File'),
        ),
        migrations.AlterField(
            model_name='mediacontent',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_pdf_file, common.validators.validate_no_executable_file], verbose_name='Media File'),
        ),
        migrations.AlterField(
            model_name='mission',
            name='image_or_video',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Mission Image/Video'),
        ),
        migrations.AlterField(
            model_name='moment',
            name='moment_file',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_pdf_file, common.validators.validate_no_executable_file], verbose_name='Image/Video'),
        ),
        migrations.AlterField(
            model_name='pray',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file], verbose_name='Pray Image'),
        ),
        migrations.AlterField(
            model_name='preach',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file], verbose_name='Lesson Image'),
        ),
        migrations.AlterField(
            model_name='preach',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Lesson Video'),
        ),
        migrations.AlterField(
            model_name='serviceevent',
            name='event_banner',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file], verbose_name='Event Banner'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_audio_file, common.validators.validate_no_executable_file], verbose_name='Testimony Audio'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='thumbnail_1',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Thumbnail 1'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='thumbnail_2',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Thumbnail 2'),
        ),
        migrations.AlterField(
            model_name='testimony',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Testimony Video'),
        ),
        migrations.AlterField(
            model_name='worship',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_audio_file, common.validators.validate_no_executable_file], verbose_name='Worship Audio'),
        ),
        migrations.AlterField(
            model_name='worship',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Worship Image'),
        ),
        migrations.AlterField(
            model_name='worship',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Worship Video'),
        ),
    ]
