from django.db import models


class Status(models.TextChoices):
    """Shared status vocabulary for Device.latest_status and Payload.status.

    UNKNOWN exists so a row can be persisted before — or despite a failure in —
    the decode step, which keeps persistence and decoding independently
    orderable instead of forcing a decode inside save().
    """

    PASSING = 'passing', 'Passing'
    FAILING = 'failing', 'Failing'
    UNKNOWN = 'unknown', 'Unknown'


class Device(models.Model):
    # The natural key payloads arrive with, but not the primary key: keeping the
    # default BigAutoField pk holds the FK column at 8 bytes and lets a devEUI
    # correction happen without cascading. unique=True supplies the lookup index.
    #
    # No format validator here on purpose. A model validator propagates into
    # ModelSerializer, which would inject validation behaviour — and an error
    # shape — into the ingest endpoint before it is written. That is a seam for
    # whoever builds the serializer.
    dev_eui = models.CharField(max_length=16, unique=True)
    acceptedRanges = models.JSONField(default=dict, blank=True)
    latest_status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.UNKNOWN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.dev_eui


class DeviceFailure(models.Model):
    device = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name='failures'
    )
    failure_type = models.CharField(
        max_length=32,
        choices=[
            ('inactivity', 'Inactivity'),
            ('out_of_range', 'Out of Range'),
            ('frequency_anomaly', 'Frequency Anomaly'),
        ],
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-detected_at',)
        indexes = [
            models.Index(fields=('device', 'resolved_at'), name='device_failures_active_idx'),
        ]

    def __str__(self):
        return f'{self.device.dev_eui} {self.failure_type}'


class Payload(models.Model):
    device = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name='payloads'
    )
    # A LoRaWAN frame counter is 32-bit unsigned (max 4294967295), which
    # overflows the Postgres `integer` that PositiveIntegerField maps to.
    f_cnt = models.PositiveBigIntegerField()
    # Fields are snake_case even though the wire format is camelCase (fCnt,
    # devEUI, rxInfo, txInfo) — that rename belongs in the serializer. `data` is
    # already snake-case-clean, so it keeps its wire name rather than gaining a
    # mapping for no readability gain. Stored verbatim so the decode stays
    # re-runnable and debuggable.
    data = models.TextField()
    object = models.JSONField(default=dict, blank=True)
    decoded_hex = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.UNKNOWN
    )
    rx_info = models.JSONField(default=list, blank=True)
    tx_info = models.JSONField(default=dict, blank=True)
    # Device/gateway-reported time, nullable because the inbound payload carries
    # no top-level timestamp — the only time present is rxInfo[0].time, and
    # pulling it out is parsing work that can land later with no schema change.
    received_at = models.DateTimeField(null=True, blank=True)
    # Server ingest time, deliberately distinct from the device's claimed time.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            # Duplicate detection, scoped per device: two devices legitimately
            # both send fCnt 100. A DB constraint rather than only a check in the
            # view, because it also holds under concurrent POSTs of one message.
            #
            # Known simplification: a frame counter is not unique per device
            # forever — it resets to 0 on rejoin and wraps at its width — so this
            # will eventually reject a legitimate post-reset payload. Two escape
            # hatches without a redesign: add a session/epoch column to `fields`,
            # or catch IntegrityError in the view and answer 200/409 on purpose
            # rather than letting it 500.
            models.UniqueConstraint(
                fields=('device', 'f_cnt'), name='unique_device_f_cnt'
            ),
        ]
        indexes = [
            # The one query the unique constraint's btree does not serve: "most
            # recent payload for this device", i.e. how latest_status gets kept
            # up to date.
            models.Index(
                fields=('device', '-created_at'), name='payload_device_recent_idx'
            ),
        ]

    def __str__(self):
        return f'{self.device.dev_eui} fCnt={self.f_cnt}'
