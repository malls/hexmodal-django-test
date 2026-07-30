from django.db import IntegrityError, transaction
from django.views.generic import TemplateView
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Device, Payload, DeviceHealthConfig
from .serializers import (
    PayloadIngestSerializer,
    DeviceDetailSerializer,
    DeviceListSerializer,
    DeviceHealthConfigSerializer,
)
from .services import decode_payload, extract_received_at, check_payload_out_of_range, check_payload_failing


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
                # Check for failures: payload failing status and sensor readings
                check_payload_failing(payload)
                check_payload_out_of_range(payload)
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


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Device.objects.prefetch_related('failures')
    filter_backends = [SearchFilter]
    search_fields = ['dev_eui']
    ordering_fields = ['dev_eui', 'latest_status', 'updated_at']
    ordering = ['dev_eui']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DeviceDetailSerializer
        return DeviceListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        failure_types = self.request.query_params.get('failure_type')
        if failure_types:
            types = [t.strip() for t in failure_types.split(',')]
            queryset = queryset.filter(
                failures__failure_type__in=types,
                failures__resolved_at__isnull=True
            ).distinct()
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(latest_status=status)
        return queryset


class DeviceHealthConfigViewSet(viewsets.ModelViewSet):
    queryset = DeviceHealthConfig.objects.all()
    serializer_class = DeviceHealthConfigSerializer
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        device_id = self.request.query_params.get('device_id')
        if device_id:
            return self.queryset.filter(device_id=device_id)
        return self.queryset


class DevicesSearchView(TemplateView):
    template_name = 'telemetry/devices_search.html'


class DeviceDetailView(TemplateView):
    template_name = 'telemetry/device_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['device_id'] = kwargs.get('device_id')
        return context
