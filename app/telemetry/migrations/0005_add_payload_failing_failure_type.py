# Generated migration for adding payload_failing failure type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telemetry', '0004_devicehealthconfig'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicefailure',
            name='failure_type',
            field=models.CharField(
                choices=[
                    ('payload_failing', 'Payload Failing'),
                    ('inactivity', 'Inactivity'),
                    ('out_of_range', 'Out of Range'),
                    ('frequency_anomaly', 'Frequency Anomaly'),
                ],
                max_length=32,
            ),
        ),
    ]
