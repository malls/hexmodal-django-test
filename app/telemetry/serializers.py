import base64
import binascii

from rest_framework import serializers


class PayloadIngestSerializer(serializers.Serializer):
    """Validates the inbound wire payload and maps camelCase to snake_case.

    A plain Serializer, not a ModelSerializer: nearly every field needs a
    source= rename and devEUI is not a Payload field at all (it resolves to
    the device FK), so field introspection buys nothing. Deliberately no
    (device, f_cnt) uniqueness pre-check here — it would race under
    concurrent POSTs, so the DB constraint plus the view's IntegrityError
    handling is the single source of truth for duplicates.
    """

    fCnt = serializers.IntegerField(source='f_cnt', min_value=0)
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
