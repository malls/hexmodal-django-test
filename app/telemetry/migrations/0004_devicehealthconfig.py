# Generated migration for DeviceHealthConfig

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telemetry', '0003_devicefailure'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceHealthConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inactivity_window_seconds', models.IntegerField(default=3600)),
                ('temp_min', models.FloatField(default=-10.0)),
                ('temp_max', models.FloatField(default=50.0)),
                ('humidity_min', models.FloatField(default=0.0)),
                ('humidity_max', models.FloatField(default=100.0)),
                ('expected_frequency_seconds', models.IntegerField(default=600)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('device', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='health_config', to='telemetry.device')),
            ],
            options={
                'verbose_name': 'Device Health Configuration',
                'verbose_name_plural': 'Device Health Configurations',
            },
        ),
    ]
