"""Black-box e2e tests for POST /api/payloads/ against the compose stack.

Every test uses a fresh uuid4-derived devEUI, so the suite is re-runnable
forever against the persistent Postgres volume with no cleanup.
"""


def body(dev_eui, f_cnt=100, data='AQ=='):
    """The PROMPT.md example payload with the variable fields swapped in."""
    return {
        'fCnt': f_cnt,
        'devEUI': dev_eui,
        'data': data,
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


def test_happy_path_prompt_example(api, fresh_dev_eui):
    response = api.post('/api/payloads/', data=body(fresh_dev_eui))

    assert response.status == 201
    result = response.json()
    assert isinstance(result['id'], int)
    assert result['devEUI'] == fresh_dev_eui
    assert result['fCnt'] == 100
    assert result['status'] == 'passing'
    assert result['decodedHex'] == '01'
    assert result['receivedAt'] == '2022-07-19T11:00:00Z'


def test_duplicate_f_cnt_same_device_is_409(api, fresh_dev_eui):
    assert api.post('/api/payloads/', data=body(fresh_dev_eui)).status == 201

    response = api.post('/api/payloads/', data=body(fresh_dev_eui))

    assert response.status == 409
    assert response.json()['detail'] == (
        f'Duplicate payload: fCnt 100 already recorded for device '
        f'{fresh_dev_eui}.'
    )


def test_same_f_cnt_different_device_is_201(api, fresh_dev_eui):
    other_dev_eui = fresh_dev_eui[::-1]

    assert api.post('/api/payloads/', data=body(fresh_dev_eui)).status == 201
    response = api.post('/api/payloads/', data=body(other_dev_eui))

    assert response.status == 201


def test_latest_status_flips_in_db(api, fresh_dev_eui, get_device_status):
    response = api.post(
        '/api/payloads/', data=body(fresh_dev_eui, f_cnt=1, data='AA==')
    )
    assert response.status == 201
    assert response.json()['status'] == 'failing'
    assert get_device_status(fresh_dev_eui) == 'failing'

    response = api.post(
        '/api/payloads/', data=body(fresh_dev_eui, f_cnt=2, data='AQ==')
    )
    assert response.status == 201
    assert response.json()['status'] == 'passing'
    assert get_device_status(fresh_dev_eui) == 'passing'


def test_no_token_is_401(anon_api, fresh_dev_eui):
    response = anon_api.post('/api/payloads/', data=body(fresh_dev_eui))

    assert response.status == 401
    assert 'detail' in response.json()


def test_wrong_token_is_401(playwright, base_url, fresh_dev_eui):
    context = playwright.request.new_context(
        base_url=base_url,
        extra_http_headers={'Authorization': 'Token not-a-real-token'},
    )
    try:
        response = context.post('/api/payloads/', data=body(fresh_dev_eui))
    finally:
        context.dispose()

    assert response.status == 401


def test_malformed_base64_is_400(api, fresh_dev_eui):
    response = api.post(
        '/api/payloads/', data=body(fresh_dev_eui, data='!!!not-base64!!!')
    )

    assert response.status == 400
    assert response.json() == {'data': ['Not valid base64.']}


def test_f_cnt_over_bigint_is_400(api, fresh_dev_eui):
    # Regression pin from the HDT-7 review: values past the bigint column
    # ceiling must be a validation 400, not a DB-level 500.
    response = api.post('/api/payloads/', data=body(fresh_dev_eui, f_cnt=2**63))

    assert response.status == 400
    assert 'fCnt' in response.json()
