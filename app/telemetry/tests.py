import datetime

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Device, Payload, Status


def example_body():
    """A fresh copy of the PROMPT.md example payload."""
    return {
        'fCnt': 100,
        'devEUI': 'abcdabcdabcdabcd',
        'data': 'AQ==',
        'rxInfo': [
            {
                'gatewayID': '1234123412341234',
                'name': 'G1',
                'time': '2022-07-19T11:00:00',
                'rssi': -57,
                'loRaSNR': 10,
            }
        ],
        'txInfo': {'frequency': 86810000, 'dr': 5},
    }


class PayloadIngestTests(APITestCase):
    def setUp(self):
        self.url = reverse('telemetry:payload-ingest')
        user = User.objects.create_user(username='ingest', password='x')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_happy_path_prompt_example(self):
        response = self.client.post(self.url, example_body(), format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        payload = Payload.objects.get()
        # Raw base64 stays verbatim so the decode is re-runnable.
        self.assertEqual(payload.data, 'AQ==')
        self.assertEqual(payload.decoded_hex, '01')
        self.assertEqual(payload.status, Status.PASSING)
        self.assertEqual(payload.f_cnt, 100)
        device = Device.objects.get()
        self.assertEqual(device.dev_eui, 'abcdabcdabcdabcd')
        self.assertEqual(device.latest_status, Status.PASSING)
        body = response.json()
        self.assertEqual(body['devEUI'], 'abcdabcdabcdabcd')
        self.assertEqual(body['fCnt'], 100)
        self.assertEqual(body['status'], 'passing')
        self.assertEqual(body['decodedHex'], '01')
        self.assertEqual(body['id'], payload.id)

    def test_received_at_parsed_from_rx_info_assuming_utc(self):
        self.client.post(self.url, example_body(), format='json')

        payload = Payload.objects.get()
        self.assertEqual(
            payload.received_at,
            datetime.datetime(
                2022, 7, 19, 11, 0, 0, tzinfo=datetime.timezone.utc
            ),
        )

    def test_empty_rx_info_leaves_received_at_null(self):
        body = example_body()
        body['rxInfo'] = []
        response = self.client.post(self.url, body, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIsNone(Payload.objects.get().received_at)

    def test_duplicate_f_cnt_same_device_conflicts(self):
        self.client.post(self.url, example_body(), format='json')
        duplicate = example_body()
        duplicate['data'] = 'AA=='  # different data, same (device, fCnt)
        response = self.client.post(self.url, duplicate, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertIn('detail', response.json())
        self.assertEqual(Payload.objects.count(), 1)
        # The rejected frame must not leak into device state.
        self.assertEqual(Device.objects.get().latest_status, Status.PASSING)

    def test_same_f_cnt_different_device_allowed(self):
        self.client.post(self.url, example_body(), format='json')
        other = example_body()
        other['devEUI'] = 'ffffffffffffffff'
        response = self.client.post(self.url, other, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(Payload.objects.count(), 2)
        self.assertEqual(Device.objects.count(), 2)

    def test_failing_value_marks_payload_and_device_failing(self):
        body = example_body()
        body['data'] = 'AA=='
        response = self.client.post(self.url, body, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        payload = Payload.objects.get()
        self.assertEqual(payload.decoded_hex, '00')
        self.assertEqual(payload.status, Status.FAILING)
        self.assertEqual(Device.objects.get().latest_status, Status.FAILING)

    def test_multi_byte_value_one_passes(self):
        # b'\x00\x01' — integer value 1 despite the leading zero byte. Pins
        # the value-semantics rule from the plan.
        body = example_body()
        body['data'] = 'AAE='
        response = self.client.post(self.url, body, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        payload = Payload.objects.get()
        self.assertEqual(payload.decoded_hex, '0001')
        self.assertEqual(payload.status, Status.PASSING)

    def test_malformed_base64_rejected(self):
        body = example_body()
        body['data'] = '!!!not-base64!!!'
        response = self.client.post(self.url, body, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payload.objects.count(), 0)
        self.assertEqual(Device.objects.count(), 0)

    def test_f_cnt_above_bigint_range_rejected(self):
        # One past the bigint column ceiling: must be a 400 from validation,
        # not a DataError 500 at insert time.
        body = example_body()
        body['fCnt'] = 2 ** 63
        response = self.client.post(self.url, body, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('fCnt', response.json())
        self.assertEqual(Payload.objects.count(), 0)

    def test_missing_required_fields_rejected(self):
        body = example_body()
        del body['data']
        del body['fCnt']
        response = self.client.post(self.url, body, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        errors = response.json()
        self.assertIn('data', errors)
        self.assertIn('fCnt', errors)

    def test_unauthenticated_rejected(self):
        self.client.credentials()
        response = self.client.post(self.url, example_body(), format='json')

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Payload.objects.count(), 0)

    def test_existing_device_reused_and_status_follows_latest(self):
        self.client.post(self.url, example_body(), format='json')
        second = example_body()
        second['fCnt'] = 101
        second['data'] = 'AA=='
        response = self.client.post(self.url, second, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 2)
        self.assertEqual(Device.objects.get().latest_status, Status.FAILING)
