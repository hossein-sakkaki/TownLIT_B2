# Generated by Django 4.2.4 on 2025-05-26 17:27

import colorfield.fields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import utils.common.utils
import validators.mediaValidators.image_validators
import validators.security_validators
import validators.user_validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomUser',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('last_email_change', models.DateTimeField(blank=True, null=True, verbose_name='Last Email Change')),
                ('email_change_tokens', models.JSONField(blank=True, help_text='Stores tokens for email change verification.', null=True, verbose_name='Email Change Tokens')),
                ('mobile_number', models.CharField(blank=True, max_length=20, null=True, validators=[validators.user_validators.validate_phone_number], verbose_name='Mobile Number')),
                ('mobile_verification_code', models.CharField(blank=True, max_length=200, null=True, verbose_name='Mobile Verification Code')),
                ('mobile_verification_expiry', models.DateTimeField(blank=True, null=True)),
                ('name', models.CharField(blank=True, max_length=40, null=True, verbose_name='Name')),
                ('family', models.CharField(blank=True, max_length=40, null=True, verbose_name='Family')),
                ('username', models.CharField(blank=True, max_length=40, unique=True, verbose_name='Username')),
                ('birthday', models.DateField(blank=True, null=True, verbose_name='Birthday')),
                ('gender', models.CharField(blank=True, choices=[('Male', 'Male'), ('Female', 'Female')], max_length=6, null=True, verbose_name='Gender')),
                ('country', models.CharField(blank=True, choices=[('AF', 'Afghanistan'), ('AL', 'Albania'), ('DZ', 'Algeria'), ('AD', 'Andorra'), ('AO', 'Angola'), ('AG', 'Antigua and Barbuda'), ('AR', 'Argentina'), ('AM', 'Armenia'), ('AU', 'Australia'), ('AT', 'Austria'), ('AZ', 'Azerbaijan'), ('BS', 'Bahamas'), ('BH', 'Bahrain'), ('BD', 'Bangladesh'), ('BB', 'Barbados'), ('BY', 'Belarus'), ('BE', 'Belgium'), ('BZ', 'Belize'), ('BJ', 'Benin'), ('BT', 'Bhutan'), ('BO', 'Bolivia'), ('BA', 'Bosnia and Herzegovina'), ('BW', 'Botswana'), ('BR', 'Brazil'), ('BN', 'Brunei'), ('BG', 'Bulgaria'), ('BF', 'Burkina Faso'), ('BI', 'Burundi'), ('CV', 'Cabo Verde'), ('KH', 'Cambodia'), ('CM', 'Cameroon'), ('CA', 'Canada'), ('CF', 'Central African Republic'), ('TD', 'Chad'), ('CL', 'Chile'), ('CN', 'China'), ('CO', 'Colombia'), ('KM', 'Comoros'), ('CG', 'Congo'), ('CR', 'Costa Rica'), ('HR', 'Croatia'), ('CU', 'Cuba'), ('CY', 'Cyprus'), ('CZ', 'Czechia'), ('DK', 'Denmark'), ('DJ', 'Djibouti'), ('DM', 'Dominica'), ('DO', 'Dominican Republic'), ('EC', 'Ecuador'), ('EG', 'Egypt'), ('SV', 'El Salvador'), ('GQ', 'Equatorial Guinea'), ('ER', 'Eritrea'), ('EE', 'Estonia'), ('SZ', 'Eswatini'), ('ET', 'Ethiopia'), ('FJ', 'Fiji'), ('FI', 'Finland'), ('FR', 'France'), ('GA', 'Gabon'), ('GM', 'Gambia'), ('GE', 'Georgia'), ('DE', 'Germany'), ('GH', 'Ghana'), ('GR', 'Greece'), ('GD', 'Grenada'), ('GT', 'Guatemala'), ('GN', 'Guinea'), ('GW', 'Guinea-Bissau'), ('GY', 'Guyana'), ('HT', 'Haiti'), ('VA', 'Holy See'), ('HN', 'Honduras'), ('HU', 'Hungary'), ('IS', 'Iceland'), ('IN', 'India'), ('ID', 'Indonesia'), ('IR', 'Iran'), ('IQ', 'Iraq'), ('IE', 'Ireland'), ('IL', 'Israel'), ('IT', 'Italy'), ('JM', 'Jamaica'), ('JP', 'Japan'), ('JO', 'Jordan'), ('KZ', 'Kazakhstan'), ('KE', 'Kenya'), ('KI', 'Kiribati'), ('KP', 'Korea (North)'), ('KR', 'Korea (South)'), ('XK', 'Kosovo'), ('KW', 'Kuwait'), ('KG', 'Kyrgyzstan'), ('LA', 'Laos'), ('LV', 'Latvia'), ('LB', 'Lebanon'), ('LS', 'Lesotho'), ('LR', 'Liberia'), ('LY', 'Libya'), ('LI', 'Liechtenstein'), ('LT', 'Lithuania'), ('LU', 'Luxembourg'), ('MG', 'Madagascar'), ('MW', 'Malawi'), ('MY', 'Malaysia'), ('MV', 'Maldives'), ('ML', 'Mali'), ('MT', 'Malta'), ('MH', 'Marshall Islands'), ('MR', 'Mauritania'), ('MU', 'Mauritius'), ('MX', 'Mexico'), ('FM', 'Micronesia'), ('MD', 'Moldova'), ('MC', 'Monaco'), ('MN', 'Mongolia'), ('ME', 'Montenegro'), ('MA', 'Morocco'), ('MZ', 'Mozambique'), ('MM', 'Myanmar'), ('NA', 'Namibia'), ('NR', 'Nauru'), ('NP', 'Nepal'), ('NL', 'Netherlands'), ('NZ', 'New Zealand'), ('NI', 'Nicaragua'), ('NE', 'Niger'), ('NG', 'Nigeria'), ('MK', 'North Macedonia'), ('NO', 'Norway'), ('OM', 'Oman'), ('PK', 'Pakistan'), ('PW', 'Palau'), ('PS', 'Palestine'), ('PA', 'Panama'), ('PG', 'Papua New Guinea'), ('PY', 'Paraguay'), ('PE', 'Peru'), ('PH', 'Philippines'), ('PL', 'Poland'), ('PT', 'Portugal'), ('QA', 'Qatar'), ('RO', 'Romania'), ('RU', 'Russia'), ('RW', 'Rwanda'), ('KN', 'Saint Kitts and Nevis'), ('LC', 'Saint Lucia'), ('VC', 'Saint Vincent and the Grenadines'), ('WS', 'Samoa'), ('SM', 'San Marino'), ('ST', 'Sao Tome and Principe'), ('SA', 'Saudi Arabia'), ('SN', 'Senegal'), ('RS', 'Serbia'), ('SC', 'Seychelles'), ('SL', 'Sierra Leone'), ('SG', 'Singapore'), ('SK', 'Slovakia'), ('SI', 'Slovenia'), ('SB', 'Solomon Islands'), ('SO', 'Somalia'), ('ZA', 'South Africa'), ('SS', 'South Sudan'), ('ES', 'Spain'), ('LK', 'Sri Lanka'), ('SD', 'Sudan'), ('SR', 'Suriname'), ('SE', 'Sweden'), ('CH', 'Switzerland'), ('SY', 'Syria'), ('TW', 'Taiwan'), ('TJ', 'Tajikistan'), ('TZ', 'Tanzania'), ('TH', 'Thailand'), ('TL', 'Timor-Leste'), ('TG', 'Togo'), ('TO', 'Tonga'), ('TT', 'Trinidad and Tobago'), ('TN', 'Tunisia'), ('TR', 'Turkey'), ('TM', 'Turkmenistan'), ('TV', 'Tuvalu'), ('UG', 'Uganda'), ('UA', 'Ukraine'), ('AE', 'United Arab Emirates'), ('GB', 'United Kingdom'), ('US', 'United States'), ('UY', 'Uruguay'), ('UZ', 'Uzbekistan'), ('VU', 'Vanuatu'), ('VE', 'Venezuela'), ('VN', 'Vietnam'), ('YE', 'Yemen'), ('ZM', 'Zambia'), ('ZW', 'Zimbabwe')], max_length=2, null=True, verbose_name='Country')),
                ('city', models.CharField(blank=True, max_length=100, null=True, verbose_name='City')),
                ('primary_language', models.CharField(choices=[('en', 'English'), ('af', 'Afrikaans'), ('sq', 'Albanian'), ('am', 'Amharic'), ('ar', 'Arabic'), ('hy', 'Armenian'), ('az', 'Azerbaijani'), ('eu', 'Basque'), ('bn', 'Bengali'), ('bs', 'Bosnian'), ('bg', 'Bulgarian'), ('my', 'Burmese'), ('ca', 'Catalan'), ('zh', 'Chinese'), ('hr', 'Croatian'), ('cs', 'Czech'), ('da', 'Danish'), ('nl', 'Dutch'), ('et', 'Estonian'), ('tl', 'Filipino'), ('fi', 'Finnish'), ('fr', 'French'), ('ka', 'Georgian'), ('de', 'German'), ('el', 'Greek'), ('gu', 'Gujarati'), ('ha', 'Hausa'), ('he', 'Hebrew'), ('hi', 'Hindi'), ('hu', 'Hungarian'), ('is', 'Icelandic'), ('ig', 'Igbo'), ('id', 'Indonesian'), ('ga', 'Irish'), ('it', 'Italian'), ('ja', 'Japanese'), ('jv', 'Javanese'), ('kn', 'Kannada'), ('kk', 'Kazakh'), ('ko', 'Korean'), ('ku', 'Kurdish'), ('ky', 'Kyrgyz'), ('lo', 'Lao'), ('lv', 'Latvian'), ('lt', 'Lithuanian'), ('mk', 'Macedonian'), ('mg', 'Malagasy'), ('ms', 'Malay'), ('ml', 'Malayalam'), ('mr', 'Marathi'), ('mn', 'Mongolian'), ('ne', 'Nepali'), ('no', 'Norwegian'), ('or', 'Oriya'), ('ps', 'Pashto'), ('fa', 'Persian'), ('pl', 'Polish'), ('pt', 'Portuguese'), ('pa', 'Punjabi'), ('ro', 'Romanian'), ('ru', 'Russian'), ('sr', 'Serbian'), ('si', 'Sinhala'), ('sk', 'Slovak'), ('sl', 'Slovenian'), ('so', 'Somali'), ('es', 'Spanish'), ('sw', 'Swahili'), ('sv', 'Swedish'), ('ta', 'Tamil'), ('te', 'Telugu'), ('th', 'Thai'), ('tr', 'Turkish'), ('uk', 'Ukrainian'), ('ur', 'Urdu'), ('uz', 'Uzbek'), ('vi', 'Vietnamese'), ('cy', 'Welsh'), ('xh', 'Xhosa'), ('yo', 'Yoruba'), ('zu', 'Zulu'), ('other', 'Other')], default='en', max_length=5, verbose_name='Primary Language')),
                ('secondary_language', models.CharField(blank=True, choices=[('en', 'English'), ('af', 'Afrikaans'), ('sq', 'Albanian'), ('am', 'Amharic'), ('ar', 'Arabic'), ('hy', 'Armenian'), ('az', 'Azerbaijani'), ('eu', 'Basque'), ('bn', 'Bengali'), ('bs', 'Bosnian'), ('bg', 'Bulgarian'), ('my', 'Burmese'), ('ca', 'Catalan'), ('zh', 'Chinese'), ('hr', 'Croatian'), ('cs', 'Czech'), ('da', 'Danish'), ('nl', 'Dutch'), ('et', 'Estonian'), ('tl', 'Filipino'), ('fi', 'Finnish'), ('fr', 'French'), ('ka', 'Georgian'), ('de', 'German'), ('el', 'Greek'), ('gu', 'Gujarati'), ('ha', 'Hausa'), ('he', 'Hebrew'), ('hi', 'Hindi'), ('hu', 'Hungarian'), ('is', 'Icelandic'), ('ig', 'Igbo'), ('id', 'Indonesian'), ('ga', 'Irish'), ('it', 'Italian'), ('ja', 'Japanese'), ('jv', 'Javanese'), ('kn', 'Kannada'), ('kk', 'Kazakh'), ('ko', 'Korean'), ('ku', 'Kurdish'), ('ky', 'Kyrgyz'), ('lo', 'Lao'), ('lv', 'Latvian'), ('lt', 'Lithuanian'), ('mk', 'Macedonian'), ('mg', 'Malagasy'), ('ms', 'Malay'), ('ml', 'Malayalam'), ('mr', 'Marathi'), ('mn', 'Mongolian'), ('ne', 'Nepali'), ('no', 'Norwegian'), ('or', 'Oriya'), ('ps', 'Pashto'), ('fa', 'Persian'), ('pl', 'Polish'), ('pt', 'Portuguese'), ('pa', 'Punjabi'), ('ro', 'Romanian'), ('ru', 'Russian'), ('sr', 'Serbian'), ('si', 'Sinhala'), ('sk', 'Slovak'), ('sl', 'Slovenian'), ('so', 'Somali'), ('es', 'Spanish'), ('sw', 'Swahili'), ('sv', 'Swedish'), ('ta', 'Tamil'), ('te', 'Telugu'), ('th', 'Thai'), ('tr', 'Turkish'), ('uk', 'Ukrainian'), ('ur', 'Urdu'), ('uz', 'Uzbek'), ('vi', 'Vietnamese'), ('cy', 'Welsh'), ('xh', 'Xhosa'), ('yo', 'Yoruba'), ('zu', 'Zulu'), ('other', 'Other')], max_length=5, null=True, verbose_name='Secondary Language')),
                ('image_name', models.ImageField(blank=True, default='media/sample/user.png', null=True, upload_to=utils.common.utils.FileUpload.dir_upload, validators=[validators.mediaValidators.image_validators.validate_image_file, validators.mediaValidators.image_validators.validate_image_size, validators.security_validators.validate_no_executable_file], verbose_name='Image')),
                ('user_active_code', models.CharField(blank=True, max_length=200, null=True)),
                ('user_active_code_expiry', models.DateTimeField(blank=True, null=True)),
                ('register_date', models.DateField(default=django.utils.timezone.now, verbose_name='Register Date')),
                ('deletion_requested_at', models.DateTimeField(blank=True, null=True, verbose_name='Deletion Requested At')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='Is Deleted')),
                ('reactivated_at', models.DateTimeField(blank=True, null=True, verbose_name='Reactivated Date')),
                ('reset_token', models.CharField(blank=True, max_length=255, null=True)),
                ('reset_token_expiration', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=False, verbose_name='Is Active')),
                ('is_admin', models.BooleanField(default=False, verbose_name='Is Admin')),
                ('is_member', models.BooleanField(default=False, verbose_name='Is Member')),
                ('is_suspended', models.BooleanField(default=False, verbose_name='Is Suspended')),
                ('reports_count', models.IntegerField(default=0, verbose_name='Reports Count')),
                ('registration_id', models.CharField(blank=True, max_length=255, null=True, verbose_name='FCM Registration ID')),
                ('two_factor_enabled', models.BooleanField(default=False, verbose_name='Two-Factor Authentication Enabled')),
                ('two_factor_token', models.CharField(blank=True, max_length=60, null=True, verbose_name='Two-Factor Token')),
                ('two_factor_token_expiry', models.DateTimeField(blank=True, null=True, verbose_name='Two-Factor Token Expiry')),
                ('pin_security_enabled', models.BooleanField(default=False, verbose_name='Pin Security Status')),
                ('access_pin', models.CharField(blank=True, max_length=255, null=True, verbose_name='Access Pin')),
                ('delete_pin', models.CharField(blank=True, max_length=255, null=True, verbose_name='Delete Pin')),
                ('show_email', models.BooleanField(default=False, verbose_name='Show Email Publicly')),
                ('show_phone_number', models.BooleanField(default=False, verbose_name='Show Phone Number Publicly')),
                ('show_country', models.BooleanField(default=False, verbose_name='Show Country Publicly')),
                ('show_city', models.BooleanField(default=False, verbose_name='Show City Publicly')),
                ('is_account_paused', models.BooleanField(default=False, verbose_name='Is Account Paused')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
            ],
            options={
                'verbose_name': '1. Custom User',
                'verbose_name_plural': '1. Custom Users',
            },
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('street_number', models.CharField(blank=True, max_length=100, verbose_name='Streen Number')),
                ('route', models.CharField(blank=True, max_length=100, verbose_name='Route')),
                ('locality', models.CharField(blank=True, max_length=100, verbose_name='Locality')),
                ('administrative_area_level_1', models.CharField(blank=True, max_length=100, verbose_name='Administrative Area Level 1')),
                ('postal_code', models.CharField(blank=True, max_length=20, verbose_name='Postal Code')),
                ('country', models.CharField(blank=True, max_length=100, verbose_name='Country')),
                ('additional', models.CharField(blank=True, max_length=400, null=True, verbose_name='Additional')),
                ('address_type', models.CharField(choices=[('home', 'Home'), ('work', 'Work'), ('office', 'Office'), ('warehouse', 'Warehouse'), ('church', 'Church'), ('school', 'School'), ('university', 'University'), ('conference_center', 'Conference Center'), ('mission_center', 'Mission Center'), ('counseling_center', 'Christian Counseling Center'), ('branch', 'Branch'), ('friends_home', "Friend's Home"), ('supplier', 'Supplier'), ('gym', 'Gym'), ('charity_center', 'Charity Center'), ('distribution_point', 'Distribution Point'), ('event_location', 'Event Location'), ('youth_center', 'Youth Center'), ('retreat_center', 'Retreat Center'), ('other', 'Other')], default='home', max_length=20, verbose_name='Address Type')),
            ],
            options={
                'verbose_name': 'Custom Address',
                'verbose_name_plural': 'Custom Addresses',
            },
        ),
        migrations.CreateModel(
            name='CustomLabel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('believer', 'I follow Jesus (Believer)'), ('seeker', 'I’m exploring faith (Seeker)'), ('prefer_not_to_say', 'I’d prefer not to say')], max_length=20, unique=True, verbose_name='Label Name')),
                ('color', colorfield.fields.ColorField(default='#FFFFFF', image_field=None, max_length=18, samples=None, verbose_name='Color Code')),
                ('description', models.CharField(blank=True, max_length=500, null=True, verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
            ],
            options={
                'verbose_name': 'Label',
                'verbose_name_plural': 'Labels',
            },
        ),
        migrations.CreateModel(
            name='SocialMediaType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('facebook', 'Facebook'), ('instagram', 'Instagram'), ('x', 'X'), ('linkedin', 'LinkedIn'), ('youtube', 'YouTube'), ('whatsapp', 'WhatsApp'), ('telegram', 'Telegram'), ('tiktok', 'TikTok'), ('pinterest', 'Pinterest'), ('snapchat', 'Snapchat'), ('discord', 'Discord'), ('twitch', 'Twitch'), ('vimeo', 'Vimeo'), ('line', 'Line'), ('vk', 'VK'), ('qq', 'QQ'), ('reddit', 'Reddit'), ('website', 'Website')], max_length=20, unique=True, verbose_name='Social Media Name')),
                ('icon_class', models.CharField(blank=True, max_length=100, null=True, verbose_name='FontAwesome Class')),
                ('icon_svg', models.TextField(blank=True, null=True, verbose_name='SVG Icon Code')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
            ],
            options={
                'verbose_name': 'Social Media Type',
                'verbose_name_plural': 'Social Media Types',
            },
        ),
        migrations.CreateModel(
            name='SocialMediaLink',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('link', models.URLField(max_length=500, verbose_name='URL Link')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('object_id', models.PositiveIntegerField(verbose_name='Object ID')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='Content Type')),
                ('social_media_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='url_links', to='accounts.socialmediatype', verbose_name='Social Media Type')),
            ],
            options={
                'verbose_name': 'URL Link',
                'verbose_name_plural': 'URL Links',
            },
        ),
        migrations.CreateModel(
            name='InviteCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('email', models.EmailField(blank=True, help_text='Optional: restrict to specific email', max_length=254, null=True)),
                ('first_name', models.CharField(blank=True, max_length=50, null=True)),
                ('last_name', models.CharField(blank=True, max_length=50, null=True)),
                ('is_used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('invite_email_sent', models.BooleanField(default=False)),
                ('invite_email_sent_at', models.DateTimeField(blank=True, null=True)),
                ('used_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='used_invite_code', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='customuser',
            name='label',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='user_label', to='accounts.customlabel', verbose_name='User Label'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='user_permissions',
            field=models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions'),
        ),
        migrations.CreateModel(
            name='UserDeviceKey',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
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
