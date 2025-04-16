# Generated by Django 4.2.4 on 2025-03-25 02:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('posts', '0001_initial'),
        ('profiles', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='worship',
            name='in_town_leaders',
            field=models.ManyToManyField(blank=True, db_index=True, to='profiles.member', verbose_name='Leaders In TownLIT'),
        ),
        migrations.AddField(
            model_name='worship',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sub_worship', to='posts.worship', verbose_name='Sub Worship'),
        ),
        migrations.AddField(
            model_name='worship',
            name='worship_resources',
            field=models.ManyToManyField(blank=True, related_name='worship_resources', to='posts.resource', verbose_name='Worship Resources'),
        ),
        migrations.AddField(
            model_name='witness',
            name='content_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='witness',
            name='testimony',
            field=models.ManyToManyField(related_name='testimony_of_member', to='posts.testimony', verbose_name='Testimony of Witness'),
        ),
        migrations.AddField(
            model_name='testimony',
            name='content_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
    ]
