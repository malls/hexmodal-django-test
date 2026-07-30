import datetime

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Device, Payload, Status, DeviceFailure, DeviceHealthConfig
from .services import check_device_inactivity, check_payload_out_of_range, check_device_frequency


def example_body():
    """A fresh copy of the PROMPT.md example payload."""
    return {
        'fCnt': 100,
        'devEUI': 'abcdabcdabcdabcd',
        'data': 'AQ==',
        "object":{"temperature": 50.5 ,"humidity": 75.0},
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


class DeviceListTests(APITestCase):
    def setUp(self):
        self.url = reverse('telemetry:device-list')
        user = User.objects.create_user(username='reader', password='x')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_list_empty(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.json()['results'], [])

    def test_list_multiple_devices(self):
        Device.objects.create(dev_eui='device1', latest_status=Status.PASSING)
        Device.objects.create(dev_eui='device2', latest_status=Status.FAILING)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = response.json()['results']
        self.assertEqual(len(results), 2)
        dev_euis = sorted([d['dev_eui'] for d in results])
        self.assertEqual(dev_euis, ['device1', 'device2'])

    def test_device_includes_failure_count(self):
        device = Device.objects.create(dev_eui='device1', latest_status=Status.PASSING)
        DeviceFailure.objects.create(device=device, failure_type='inactivity')
        DeviceFailure.objects.create(device=device, failure_type='out_of_range')
        response = self.client.get(self.url)

        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['failure_count'], 2)

    def test_resolved_failures_not_counted(self):
        device = Device.objects.create(dev_eui='device1', latest_status=Status.PASSING)
        DeviceFailure.objects.create(device=device, failure_type='inactivity')
        DeviceFailure.objects.create(
            device=device,
            failure_type='out_of_range',
            resolved_at=datetime.datetime.now(datetime.timezone.utc),
        )
        response = self.client.get(self.url)

        results = response.json()['results']
        self.assertEqual(results[0]['failure_count'], 1)

    def test_filter_by_failure_type(self):
        dev1 = Device.objects.create(dev_eui='device1')
        dev2 = Device.objects.create(dev_eui='device2')
        dev3 = Device.objects.create(dev_eui='device3')

        DeviceFailure.objects.create(device=dev1, failure_type='inactivity')
        DeviceFailure.objects.create(device=dev2, failure_type='out_of_range')
        DeviceFailure.objects.create(device=dev3, failure_type='frequency_anomaly')

        response = self.client.get(f'{self.url}?failure_type=inactivity,out_of_range')

        results = response.json()['results']
        dev_euis = sorted([d['dev_eui'] for d in results])
        self.assertEqual(dev_euis, ['device1', 'device2'])

    def test_filter_ignores_resolved_failures(self):
        dev1 = Device.objects.create(dev_eui='device1')
        dev2 = Device.objects.create(dev_eui='device2')

        DeviceFailure.objects.create(device=dev1, failure_type='inactivity')
        DeviceFailure.objects.create(
            device=dev2,
            failure_type='inactivity',
            resolved_at=datetime.datetime.now(datetime.timezone.utc),
        )

        response = self.client.get(f'{self.url}?failure_type=inactivity')

        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['dev_eui'], 'device1')

    def test_unauthenticated_rejected(self):
        self.client.credentials()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class DeviceDetailTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reader', password='x')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_retrieve_device(self):
        device = Device.objects.create(dev_eui='device1', latest_status=Status.PASSING)
        url = reverse('telemetry:device-detail', kwargs={'pk': device.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['dev_eui'], 'device1')
        self.assertEqual(data['latest_status'], 'passing')

    def test_device_detail_includes_active_failures(self):
        device = Device.objects.create(dev_eui='device1', latest_status=Status.PASSING)
        DeviceFailure.objects.create(
            device=device,
            failure_type='inactivity',
            details={'last_seen': '2026-07-30T10:00:00Z'},
        )
        DeviceFailure.objects.create(
            device=device,
            failure_type='out_of_range',
            details={'value': 100},
        )
        url = reverse('telemetry:device-detail', kwargs={'pk': device.pk})
        response = self.client.get(url)

        data = response.json()
        self.assertEqual(len(data['failures']), 2)
        failure_types = sorted([f['failure_type'] for f in data['failures']])
        self.assertEqual(failure_types, ['inactivity', 'out_of_range'])

    def test_device_detail_excludes_resolved_failures(self):
        device = Device.objects.create(dev_eui='device1', latest_status=Status.PASSING)
        DeviceFailure.objects.create(device=device, failure_type='inactivity')
        DeviceFailure.objects.create(
            device=device,
            failure_type='out_of_range',
            resolved_at=datetime.datetime.now(datetime.timezone.utc),
        )
        url = reverse('telemetry:device-detail', kwargs={'pk': device.pk})
        response = self.client.get(url)

        data = response.json()
        self.assertEqual(len(data['failures']), 1)
        self.assertEqual(data['failures'][0]['failure_type'], 'inactivity')

    def test_device_detail_404_for_nonexistent(self):
        url = reverse('telemetry:device-detail', kwargs={'pk': 9999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_rejected(self):
        device = Device.objects.create(dev_eui='device1')
        url = reverse('telemetry:device-detail', kwargs={'pk': device.pk})
        self.client.credentials()
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class DeviceHealthConfigTests(APITestCase):
    def setUp(self):
        self.url = reverse('telemetry:health-config-list')
        user = User.objects.create_user(username='admin', password='x')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.device = Device.objects.create(dev_eui='device1')

    def test_create_config_with_defaults(self):
        data = {'device': self.device.id}
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        config = DeviceHealthConfig.objects.get(device=self.device)
        self.assertEqual(config.inactivity_window_seconds, 3600)
        self.assertEqual(config.temp_min, -10.0)
        self.assertEqual(config.temp_max, 50.0)
        self.assertEqual(config.humidity_min, 0.0)
        self.assertEqual(config.humidity_max, 100.0)
        self.assertEqual(config.expected_frequency_seconds, 600)

    def test_create_config_with_custom_values(self):
        data = {
            'device': self.device.id,
            'inactivity_window_seconds': 7200,
            'temp_min': 10.0,
            'temp_max': 30.0,
            'humidity_min': 20.0,
            'humidity_max': 80.0,
            'expected_frequency_seconds': 300,
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        config = DeviceHealthConfig.objects.get(device=self.device)
        self.assertEqual(config.inactivity_window_seconds, 7200)
        self.assertEqual(config.temp_min, 10.0)
        self.assertEqual(config.temp_max, 30.0)

    def test_update_config(self):
        config = DeviceHealthConfig.objects.create(device=self.device)
        url = reverse('telemetry:health-config-detail', kwargs={'pk': config.pk})
        data = {'temp_max': 60.0, 'expected_frequency_seconds': 450}
        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.temp_max, 60.0)
        self.assertEqual(config.expected_frequency_seconds, 450)

    def test_list_configs(self):
        dev2 = Device.objects.create(dev_eui='device2')
        DeviceHealthConfig.objects.create(device=self.device)
        DeviceHealthConfig.objects.create(device=dev2)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = response.json()['results']
        self.assertEqual(len(results), 2)

    def test_filter_by_device(self):
        dev2 = Device.objects.create(dev_eui='device2')
        DeviceHealthConfig.objects.create(device=self.device)
        DeviceHealthConfig.objects.create(device=dev2)
        response = self.client.get(f'{self.url}?device_id={self.device.id}')

        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['device'], self.device.id)

    def test_validation_temp_min_max(self):
        data = {
            'device': self.device.id,
            'temp_min': 50.0,
            'temp_max': 10.0,  # Invalid: min > max
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('temp_min', str(response.json()))

    def test_validation_humidity_min_max(self):
        data = {
            'device': self.device.id,
            'humidity_min': 80.0,
            'humidity_max': 20.0,  # Invalid: min > max
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('humidity_min', str(response.json()))

    def test_validation_inactivity_positive(self):
        data = {
            'device': self.device.id,
            'inactivity_window_seconds': -100,  # Invalid: negative
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validation_frequency_positive(self):
        data = {
            'device': self.device.id,
            'expected_frequency_seconds': 0,  # Invalid: must be positive
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_retrieve_config(self):
        config = DeviceHealthConfig.objects.create(device=self.device)
        url = reverse('telemetry:health-config-detail', kwargs={'pk': config.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['device'], self.device.id)
        self.assertEqual(data['inactivity_window_seconds'], 3600)

    def test_unauthenticated_rejected(self):
        self.client.credentials()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class InactivityDetectionTests(APITestCase):
    def setUp(self):
        self.device = Device.objects.create(dev_eui='device1')
        self.config = DeviceHealthConfig.objects.create(
            device=self.device,
            inactivity_window_seconds=3600,
        )

    def test_flag_device_with_no_payloads(self):
        result = check_device_inactivity()

        self.assertEqual(len(result['flagged']), 1)
        self.assertEqual(len(result['resolved']), 0)
        failure = self.device.failures.get()
        self.assertEqual(failure.failure_type, 'inactivity')
        self.assertIsNone(failure.resolved_at)
        self.assertIn('inactivity_window_seconds', failure.details)

    def test_flag_device_with_old_payload(self):
        old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=7200
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=old_time,
        )

        result = check_device_inactivity()

        self.assertEqual(len(result['flagged']), 1)
        failure = self.device.failures.get()
        self.assertEqual(failure.failure_type, 'inactivity')

    def test_do_not_flag_device_with_recent_payload(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=1800),
        )

        result = check_device_inactivity()

        self.assertEqual(len(result['flagged']), 0)
        self.assertEqual(self.device.failures.count(), 0)

    def test_resolve_inactivity_when_device_reports(self):
        old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=7200
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=old_time,
        )
        check_device_inactivity()
        self.assertEqual(len(self.device.failures.filter(resolved_at__isnull=True)), 1)

        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_inactivity()

        self.assertEqual(len(result['resolved']), 1)
        self.assertIsNotNone(self.device.failures.get().resolved_at)

    def test_idempotent_no_duplicate_failures(self):
        check_device_inactivity()
        check_device_inactivity()
        check_device_inactivity()

        self.assertEqual(self.device.failures.count(), 1)

    def test_creates_config_if_missing(self):
        device_no_config = Device.objects.create(dev_eui='device2')
        self.assertFalse(hasattr(device_no_config, 'health_config'))

        check_device_inactivity()

        self.assertTrue(DeviceHealthConfig.objects.filter(device=device_no_config).exists())

    def test_uses_config_inactivity_window(self):
        self.config.inactivity_window_seconds = 1800
        self.config.save()

        recent_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=2000
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=recent_time,
        )

        result = check_device_inactivity()

        self.assertEqual(len(result['flagged']), 1)

    def test_details_include_last_payload_time(self):
        payload_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=7200
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=payload_time,
        )

        check_device_inactivity()

        failure = self.device.failures.get()
        self.assertIn('last_payload_time', failure.details)
        self.assertIn('checked_at', failure.details)
        self.assertIn('inactivity_window_seconds', failure.details)


class OutOfRangeDetectionTests(APITestCase):
    def setUp(self):
        self.device = Device.objects.create(dev_eui='device1')
        self.config = DeviceHealthConfig.objects.create(
            device=self.device,
            temp_min=15.0,
            temp_max=25.0,
            humidity_min=30.0,
            humidity_max=70.0,
        )

    def test_flag_temperature_too_high(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 30.0, 'humidity': 50.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        self.assertEqual(failure.failure_type, 'out_of_range')
        self.assertIn('temperature', failure.details['out_of_range_fields'])
        self.assertEqual(failure.details['temperature'], 30.0)

    def test_flag_temperature_too_low(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 10.0, 'humidity': 50.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        self.assertIn('temperature', failure.details['out_of_range_fields'])
        self.assertEqual(failure.details['temperature'], 10.0)

    def test_flag_humidity_too_high(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 20.0, 'humidity': 80.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        self.assertIn('humidity', failure.details['out_of_range_fields'])
        self.assertEqual(failure.details['humidity'], 80.0)

    def test_flag_humidity_too_low(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 20.0, 'humidity': 20.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        self.assertIn('humidity', failure.details['out_of_range_fields'])
        self.assertEqual(failure.details['humidity'], 20.0)

    def test_flag_both_temp_and_humidity_out_of_range(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 30.0, 'humidity': 80.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        self.assertEqual(len(failure.details['out_of_range_fields']), 2)
        self.assertIn('temperature', failure.details['out_of_range_fields'])
        self.assertIn('humidity', failure.details['out_of_range_fields'])

    def test_no_flag_when_readings_in_range(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 20.0, 'humidity': 50.0},
        )

        check_payload_out_of_range(payload)

        self.assertEqual(self.device.failures.count(), 0)

    def test_resolve_out_of_range_when_readings_return_to_normal(self):
        payload1 = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 30.0, 'humidity': 50.0},
        )
        check_payload_out_of_range(payload1)
        self.assertEqual(len(self.device.failures.filter(resolved_at__isnull=True)), 1)

        payload2 = Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            object={'temperature': 20.0, 'humidity': 50.0},
        )
        check_payload_out_of_range(payload2)

        failure = self.device.failures.get()
        self.assertIsNotNone(failure.resolved_at)

    def test_idempotent_no_duplicate_failures(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 30.0, 'humidity': 50.0},
        )

        check_payload_out_of_range(payload)
        check_payload_out_of_range(payload)
        check_payload_out_of_range(payload)

        self.assertEqual(self.device.failures.count(), 1)

    def test_ignore_missing_temperature(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'humidity': 50.0},
        )

        result = check_payload_out_of_range(payload)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)

    def test_ignore_missing_humidity(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 20.0},
        )

        result = check_payload_out_of_range(payload)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)

    def test_ignore_empty_readings(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={},
        )

        result = check_payload_out_of_range(payload)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)

    def test_failure_includes_config_bounds(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 30.0, 'humidity': 50.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        config = failure.details['config']
        self.assertEqual(config['temp_min'], 15.0)
        self.assertEqual(config['temp_max'], 25.0)
        self.assertEqual(config['humidity_min'], 30.0)
        self.assertEqual(config['humidity_max'], 70.0)

    def test_failure_includes_payload_id(self):
        payload = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            object={'temperature': 30.0, 'humidity': 50.0},
        )

        check_payload_out_of_range(payload)

        failure = self.device.failures.get()
        self.assertEqual(failure.details['payload_id'], payload.id)


class FrequencyAnomalyDetectionTests(APITestCase):
    def setUp(self):
        self.device = Device.objects.create(dev_eui='device1')
        self.config = DeviceHealthConfig.objects.create(
            device=self.device,
            expected_frequency_seconds=600,
        )

    def test_no_flag_with_single_payload(self):
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
        )

        result = check_device_frequency(self.device)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)

    def test_no_flag_with_frequent_payloads(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=300),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_frequency(self.device)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)

    def test_no_flag_at_exact_frequency(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=600),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_frequency(self.device)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)

    def test_flag_when_gap_exceeds_threshold(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=1000),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_frequency(self.device)

        self.assertTrue(result)
        failure = self.device.failures.get()
        self.assertEqual(failure.failure_type, 'frequency_anomaly')
        self.assertEqual(failure.details['gap_seconds'], 1000)

    def test_uses_1_5x_tolerance(self):
        self.config.expected_frequency_seconds = 600
        self.config.save()

        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=850),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_frequency(self.device)

        self.assertFalse(result)
        self.assertEqual(self.device.failures.count(), 0)
        gap = 850
        threshold = 600 * 1.5
        self.assertLess(gap, threshold)

    def test_flag_at_1_5x_threshold_plus_one_second(self):
        self.config.expected_frequency_seconds = 600
        self.config.save()

        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=901),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_frequency(self.device)

        self.assertTrue(result)

    def test_resolve_when_frequency_improves(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        p1 = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=1000),
        )
        p2 = Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        check_device_frequency(self.device)
        self.assertEqual(len(self.device.failures.filter(resolved_at__isnull=True)), 1)

        p3 = Payload.objects.create(
            device=self.device,
            f_cnt=3,
            data='AQ==',
            created_at=now + datetime.timedelta(seconds=300),
        )

        check_device_frequency(self.device)

        failure = self.device.failures.get()
        self.assertIsNotNone(failure.resolved_at)

    def test_idempotent_no_duplicate_failures(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=1000),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        check_device_frequency(self.device)
        check_device_frequency(self.device)
        check_device_frequency(self.device)

        self.assertEqual(self.device.failures.count(), 1)

    def test_failure_includes_gap_and_threshold(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        older = Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=1000),
        )
        newer = Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        check_device_frequency(self.device)

        failure = self.device.failures.get()
        self.assertEqual(failure.details['gap_seconds'], 1000)
        self.assertEqual(failure.details['expected_frequency_seconds'], 600)
        self.assertEqual(failure.details['threshold_seconds'], 900)
        self.assertEqual(failure.details['older_payload_id'], older.id)
        self.assertEqual(failure.details['newer_payload_id'], newer.id)

    def test_with_custom_expected_frequency(self):
        self.config.expected_frequency_seconds = 300
        self.config.save()

        now = datetime.datetime.now(datetime.timezone.utc)
        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=500),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        result = check_device_frequency(self.device)

        self.assertTrue(result)
        failure = self.device.failures.get()
        self.assertEqual(failure.details['expected_frequency_seconds'], 300)
        self.assertEqual(failure.details['threshold_seconds'], 450)

    def test_independent_device_frequencies(self):
        device2 = Device.objects.create(dev_eui='device2')
        DeviceHealthConfig.objects.create(
            device=device2,
            expected_frequency_seconds=600,
        )

        now = datetime.datetime.now(datetime.timezone.utc)

        Payload.objects.create(
            device=self.device,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=1000),
        )
        Payload.objects.create(
            device=self.device,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        Payload.objects.create(
            device=device2,
            f_cnt=1,
            data='AQ==',
            created_at=now - datetime.timedelta(seconds=300),
        )
        Payload.objects.create(
            device=device2,
            f_cnt=2,
            data='AQ==',
            created_at=now,
        )

        check_device_frequency(self.device)
        check_device_frequency(device2)

        self.assertEqual(self.device.failures.count(), 1)
        self.assertEqual(device2.failures.count(), 0)
