# Generated migration for setup wizard models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_remove_feature_flags_tables'),
    ]

    operations = [
        migrations.CreateModel(
            name='SetupStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('setup_version', models.CharField(default='1.0', max_length=10)),
                ('features_enabled', models.JSONField(blank=True, default=dict)),
                ('setup_data', models.JSONField(blank=True, default=dict, help_text='Additional setup configuration')),
            ],
            options={
                'verbose_name_plural': 'Setup Status',
                'db_table': 'setup_status',
            },
        ),
        migrations.CreateModel(
            name='FeatureFlag',
            fields=[
                ('studio', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='features', serialize=False, to='core.studio')),
                ('billing_enabled', models.BooleanField(default=True, help_text='Enable billing and invoicing features')),
                ('inventory_enabled', models.BooleanField(default=True, help_text='Enable inventory management')),
                ('messaging_enabled', models.BooleanField(default=True, help_text='Enable internal messaging system')),
                ('resources_enabled', models.BooleanField(default=True, help_text='Enable resources library')),
                ('goals_enabled', models.BooleanField(default=True, help_text='Enable student goals tracking')),
                ('bands_enabled', models.BooleanField(default=True, help_text='Enable bands/ensembles management')),
                ('analytics_enabled', models.BooleanField(default=True, help_text='Enable analytics and reports')),
                ('practice_rooms_enabled', models.BooleanField(default=True, help_text='Enable practice room booking')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Feature Flag',
                'verbose_name_plural': 'Feature Flags',
                'db_table': 'feature_flags',
            },
        ),
    ]
