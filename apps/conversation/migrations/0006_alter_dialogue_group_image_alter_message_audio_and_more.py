# Generated by Django 4.2.4 on 2025-04-09 04:00

import common.validators
from django.db import migrations, models
import django.db.models.deletion
import utils


class Migration(migrations.Migration):

    dependencies = [
        ('conversation', '0005_remove_message_content_plaintext_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dialogue',
            name='group_image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, validators=[common.validators.validate_image_or_video_file, common.validators.validate_no_executable_file], verbose_name='Group Image'),
        ),
        migrations.AlterField(
            model_name='message',
            name='audio',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, verbose_name='Audio'),
        ),
        migrations.AlterField(
            model_name='message',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, verbose_name='File'),
        ),
        migrations.AlterField(
            model_name='message',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, verbose_name='Image'),
        ),
        migrations.AlterField(
            model_name='message',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=utils.FileUpload.dir_upload, verbose_name='Video'),
        ),
        migrations.CreateModel(
            name='MessageEncryption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_id', models.CharField(max_length=255)),
                ('encrypted_content', models.TextField()),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encryptions', to='conversation.message')),
            ],
        ),
    ]
