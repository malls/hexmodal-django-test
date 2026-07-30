import base64
import binascii

from rest_framework import serializers

from .models import Device, DeviceFailure, Payload


class PayloadIngestSerializer(serializers.Serializer):
    """Validates the inbound wire payload and maps camelCase to snake_case.

    A plain Serializer, not a ModelSerializer: nearly every field needs a
    source= rename and devEUI is not a Payload field at all (it resolves to
    the device FK), so field introspection buys nothing. Deliberately no
    (device, f_cnt) uniqueness pre-check here — it would race under
    concurrent POSTs, so the DB constraint plus the view's IntegrityError
    handling is the single source of truth for duplicates.
    """

    # Bounds mirror the PositiveBigIntegerField column exactly: min_value=0
    # matches its check constraint, max_value the bigint ceiling — so an
    # absurd counter is a 400 here, not a DataError 500 at insert time.
    fCnt = serializers.IntegerField(
        source='f_cnt', min_value=0, max_value=9223372036854775807
    )
    # No hex-format validation: the model left devEUI format policy open on
    # purpose, and a permissive ingest keeps working when a vendor sends
    # uppercase or otherwise nonstandard EUIs. max_length matches the column
    # so the DB can never reject what validation accepted.
    devEUI = serializers.CharField(source='dev_eui', max_length=16)
    data = serializers.CharField()
    # ListField/DictField rather than JSONField so a wrongly-typed body is a
    # 400 here instead of a TypeError when the view indexes rx_info[0].
    rxInfo = serializers.ListField(source='rx_info', required=False, default=list)
    txInfo = serializers.DictField(source='tx_info', required=False, default=dict)

    def validate_data(self, value):
        try:
            raw = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError('Not valid base64.')
        # decoded_hex is CharField(max_length=64) = 32 bytes; without this
        # bound an oversized payload becomes a DB error (500) instead of a 400.
        if len(raw) > 32:
            raise serializers.ValidationError(
                'Decoded payload exceeds 32 bytes.'
            )
        return value


class DeviceFailureSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceFailure
        fields = ('id', 'failure_type', 'detected_at', 'resolved_at', 'details')


class DeviceListSerializer(serializers.ModelSerializer):
    failure_count = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ('id', 'dev_eui', 'latest_status', 'created_at', 'updated_at', 'failure_count')

    def get_failure_count(self, obj):
        return obj.failures.filter(resolved_at__isnull=True).count()


class DeviceDetailSerializer(serializers.ModelSerializer):
    failures = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ('id', 'dev_eui', 'latest_status', 'created_at', 'updated_at', 'failures')

    def get_failures(self, obj):
        active_failures = obj.failures.filter(resolved_at__isnull=True)
        return DeviceFailureSerializer(active_failures, many=True).data
