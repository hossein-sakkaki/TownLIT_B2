# apps/ai_gateway/migrations/0001_initial.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.
# Generated with Django 5.2.18; metadata only, no data migration.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ServicePrincipal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('agent_id', models.CharField(choices=[('eli', 'eli'), ('phoebe', 'phoebe'), ('silas', 'silas'), ('lydia', 'lydia'), ('joanna', 'joanna'), ('micah', 'micah'), ('chloe', 'chloe')], max_length=16)),
                ('environment', models.CharField(max_length=32)),
                ('active', models.BooleanField(default=False)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='OfficeOrganizationBinding',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('environment', models.CharField(max_length=32)),
                ('office_organization_id', models.UUIDField()),
                ('backend_organization_id', models.UUIDField()),
                ('active', models.BooleanField(default=False)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('environment', 'office_organization_id'), name='aig_org_mapping_uq')],
            },
        ),
        migrations.CreateModel(
            name='IdempotencyReceipt',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('operation', models.CharField(max_length=80)),
                ('version', models.PositiveSmallIntegerField()),
                ('scope_ref', models.UUIDField()),
                ('key_digest', models.CharField(max_length=64)),
                ('payload_digest', models.CharField(max_length=64)),
                ('canonicalization_version', models.PositiveSmallIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.officeorganizationbinding')),
                ('principal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.serviceprincipal')),
            ],
        ),
        migrations.CreateModel(
            name='AuditEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_id', models.UUIDField()),
                ('correlation_id', models.UUIDField()),
                ('code', models.CharField(choices=[('access_denied', 'access_denied'), ('metadata_reserved', 'metadata_reserved'), ('metadata_replayed', 'metadata_replayed'), ('grant_revoked', 'grant_revoked')], max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('receipt', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.idempotencyreceipt')),
                ('organization', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.officeorganizationbinding')),
                ('principal', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.serviceprincipal')),
            ],
        ),
        migrations.CreateModel(
            name='RequestNonce',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('request', 'request'), ('assertion', 'assertion')], max_length=16)),
                ('digest', models.CharField(max_length=64)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('principal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.serviceprincipal')),
            ],
            options={
                'indexes': [models.Index(fields=['expires_at'], name='aig_nonce_exp_idx')],
                'constraints': [models.UniqueConstraint(fields=('principal', 'purpose', 'digest'), name='aig_nonce_once_uq')],
            },
        ),
        migrations.CreateModel(
            name='OperationGrant',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('operation', models.CharField(max_length=80)),
                ('version', models.PositiveSmallIntegerField()),
                ('scope_ref', models.UUIDField()),
                ('active', models.BooleanField(default=False)),
                ('expires_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.officeorganizationbinding')),
                ('principal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ai_gateway.serviceprincipal')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('principal', 'organization', 'operation', 'version', 'scope_ref'), name='aig_grant_scope_uq'), models.CheckConstraint(condition=models.Q(('version__gte', 1)), name='aig_grant_version_ck')],
            },
        ),
        migrations.AddIndex(
            model_name='idempotencyreceipt',
            index=models.Index(fields=['organization', 'created_at'], name='aig_receipt_org_idx'),
        ),
        migrations.AddConstraint(
            model_name='idempotencyreceipt',
            constraint=models.UniqueConstraint(fields=('principal', 'organization', 'operation', 'version', 'key_digest'), name='aig_receipt_key_uq'),
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['organization', 'created_at'], name='aig_audit_org_idx'),
        ),
    ]
