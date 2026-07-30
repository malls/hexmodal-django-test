# Generated migration for DeviceFailure model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telemetry', '0002_payload_object'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceFailure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('failure_type', models.CharField(choices=[('inactivity', 'Inactivity'), ('out_of_range', 'Out of Range'), ('frequency_anomaly', 'Frequency Anomaly')], max_length=32)),
                ('detected_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='failures', to='telemetry.device')),
            ],
            options={
                'ordering': ('-detected_at',),
            },
        ),
        migrations.AddIndex(
            model_name='devicefailure',
            index=models.Index(fields=('device', 'resolved_at'), name='device_failures_active_idx'),
        ),
    ]
