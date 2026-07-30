from django.db import IntegrityError, transaction
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Device, Payload
from .serializers import PayloadIngestSerializer
from .services import decode_payload, extract_received_at


class PayloadIngestView(APIView):
    """POST /api/payloads/ — ingest one uplink frame.

    Auth comes from the global DRF defaults (TokenAuthentication +
    IsAuthenticated, HDT-6); nothing endpoint-specific here.
    """

    def post(self, request):
        serializer = PayloadIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        decoded_hex, payload_status = decode_payload(validated['data'])
        received_at = extract_received_at(validated['rx_info'])

        # IntegrityError must be caught OUTSIDE the atomic block: catching it
        # inside leaves the transaction marked broken and the next query
        # raises TransactionManagementError instead of producing the 409.
        try:
            with transaction.atomic():
                # Unknown devEUIs auto-register — an ingest endpoint that
                # rejects them needs a provisioning flow that is out of scope.
                # get_or_create is savepoint-protected, so a concurrent
                # first-registration race degrades to a get, not an error.
                device, _ = Device.objects.get_or_create(
                    dev_eui=validated['dev_eui']
                )
                # Persist first with status 'unknown', then apply decode
                # results — the ordering the models were designed for. One
                # transaction, so no 'unknown' row is visible outside it.
                payload = Payload.objects.create(
                    device=device,
                    f_cnt=validated['f_cnt'],
                    data=validated['data'],
                    rx_info=validated['rx_info'],
                    tx_info=validated['tx_info'],
                    received_at=received_at,
                )
                payload.decoded_hex = decoded_hex
                payload.status = payload_status
                payload.save(update_fields=['decoded_hex', 'status'])
                # Known simplification: latest_status means "status of the
                # most recently ingested payload" — a delayed older frame
                # overwrites a newer status. Fixing that needs fCnt-guarded
                # updates plus a counter-reset policy; documented in README.
                device.latest_status = payload_status
                # save() rather than queryset .update() so auto_now still
                # touches updated_at.
                device.save(update_fields=['latest_status', 'updated_at'])
        except IntegrityError:
            return Response(
                {
                    'detail': (
                        f'Duplicate payload: fCnt {validated["f_cnt"]} already '
                        f'recorded for device {validated["dev_eui"]}.'
                    )
                },
                status=http_status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                'id': payload.id,
                'devEUI': device.dev_eui,
                'fCnt': payload.f_cnt,
                'status': payload.status,
                'decodedHex': payload.decoded_hex,
                'receivedAt': payload.received_at,
            },
            status=http_status.HTTP_201_CREATED,
        )
