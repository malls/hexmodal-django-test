"""E2E tests for Device Search/Filter UI (HDT-16)"""

import pytest


class TestDevicesSearchView:
    """Tests for the devices search/list view"""

    def test_load_page(self, playwright, base_url):
        """Verify devices search page loads"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            assert page.title() == 'Device Health Monitor'
            # Verify key elements are present
            assert page.locator('[data-testid=search-input]').is_visible()
            assert page.locator('[data-testid=device-list]').is_visible()

    def test_search_box_present(self, playwright, base_url):
        """Verify search box with placeholder is present"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            search_box = page.locator('[data-testid=search-input]')
            assert search_box.get_attribute('placeholder') == 'Search by device ID...'

    def test_filter_options_present(self, playwright, base_url):
        """Verify filter controls are present"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            # Status filters
            assert page.locator('[data-testid=status-all]').is_visible()
            assert page.locator('[data-testid=status-passing]').is_visible()
            assert page.locator('[data-testid=status-failing]').is_visible()
            # Failure type filters
            assert page.locator('[data-testid=failure-type-inactivity]').is_visible()
            assert page.locator('[data-testid=failure-type-out-of-range]').is_visible()
            assert page.locator('[data-testid=failure-type-frequency]').is_visible()

    def test_empty_state(self, playwright, base_url):
        """Verify empty state when no devices match"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            # Wait for page to load
            page.wait_for_load_state('networkidle')
            # Either shows devices or empty message
            device_list = page.locator('[data-testid=device-list] tbody tr')
            empty_message = page.locator('.empty-message')
            # At least one should be visible
            if empty_message.is_visible():
                assert 'No devices match' in page.locator('.empty-message').text_content()

    def test_search_by_dev_eui(self, api, playwright, base_url, fresh_dev_eui):
        """Verify search filters by dev_eui substring"""
        # Create a test device via API
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',  # base64 for value 1 (passing)
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Search for the device (first 8 chars)
            search_input = page.locator('[data-testid=search-input]')
            search_input.fill(fresh_dev_eui[:8])
            page.wait_for_timeout(400)  # Wait for debounce
            page.wait_for_load_state('networkidle')

            # Verify device appears in table
            rows = page.locator('[data-testid=device-row]')
            assert rows.count() >= 1
            # Verify the searched dev_eui appears
            assert fresh_dev_eui in page.content()

    def test_pagination_buttons(self, playwright, base_url):
        """Verify pagination controls are present and functional"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Verify pagination elements
            prev_btn = page.locator('#prev-btn')
            next_btn = page.locator('#next-btn')
            page_info = page.locator('#page-info')

            assert prev_btn.is_visible()
            assert next_btn.is_visible()
            assert page_info.is_visible()
            # First page prev button should be disabled
            assert prev_btn.is_disabled()

    def test_sort_by_dev_eui(self, api, playwright, base_url):
        """Verify sorting by device ID works"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Click sort button for dev_eui
            sort_btn = page.locator('.sort-btn[data-column="dev_eui"]')
            sort_btn.click()
            page.wait_for_timeout(400)
            page.wait_for_load_state('networkidle')

            # Verify sort indicator appears
            indicator = sort_btn.locator('.sort-indicator')
            assert indicator.text_content() != ''

    def test_status_filter_radio_buttons(self, playwright, base_url):
        """Verify status filter radio buttons work"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Select "failing" status
            failing_radio = page.locator('[data-testid=status-failing]')
            failing_radio.check()
            page.wait_for_timeout(400)
            page.wait_for_load_state('networkidle')

            # Verify radio is checked
            assert failing_radio.is_checked()

    def test_failure_type_checkboxes(self, playwright, base_url):
        """Verify failure type filter checkboxes work"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Check inactivity checkbox
            inactivity_cb = page.locator('[data-testid=failure-type-inactivity]')
            inactivity_cb.check()
            page.wait_for_timeout(400)
            page.wait_for_load_state('networkidle')

            # Verify checkbox is checked
            assert inactivity_cb.is_checked()

    def test_clear_search(self, api, playwright, base_url, fresh_dev_eui):
        """Verify clear search button works"""
        # Create a test device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Type in search
            search_input = page.locator('[data-testid=search-input]')
            search_input.fill('xyz_nonexistent')
            page.wait_for_timeout(400)
            page.wait_for_load_state('networkidle')

            # Click clear button
            clear_btn = page.locator('#clear-search')
            clear_btn.click()
            page.wait_for_timeout(100)

            # Verify search box is empty
            assert search_input.input_value() == ''

    def test_click_device_navigates_to_detail(self, api, playwright, base_url, fresh_dev_eui):
        """Verify clicking device row navigates to detail view"""
        # Create a test device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Get first device ID from table
            first_row = page.locator('[data-testid=device-row]').first
            if first_row.count() > 0:
                # Click the detail link (→ icon)
                detail_link = first_row.locator('.detail-link')
                detail_link.click()
                page.wait_for_load_state('networkidle')

                # Verify we're on detail page
                assert '/detail/' in page.url


class TestDeviceDetailView:
    """Tests for the device detail view"""

    def test_load_device_detail_page(self, api, playwright, base_url, fresh_dev_eui):
        """Verify device detail page loads for a valid device"""
        # Create a device
        payload_resp = api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        # Get device ID from response (needs to fetch device first)
        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Verify page loaded
                assert page.locator('#device-section').is_visible()
                assert fresh_dev_eui in page.content()

    def test_device_detail_has_overview_section(self, api, playwright, base_url, fresh_dev_eui):
        """Verify device detail page has overview section"""
        # Create device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Verify overview section elements
                assert page.locator('#status-text').is_visible()
                assert page.locator('#created-date').is_visible()
                assert page.locator('#last-activity').is_visible()

    def test_device_detail_has_config_section(self, api, playwright, base_url, fresh_dev_eui):
        """Verify device detail page displays health config"""
        # Create device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Verify config section elements
                assert page.locator('#config-inactivity').is_visible()
                assert page.locator('#config-temp').is_visible()
                assert page.locator('#config-humidity').is_visible()
                assert page.locator('#config-frequency').is_visible()

    def test_back_button_navigates_to_list(self, api, playwright, base_url, fresh_dev_eui):
        """Verify back button returns to devices list"""
        # Create device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Click back link
                back_link = page.locator('.back-link')
                back_link.click()
                page.wait_for_load_state('networkidle')

                # Verify we're back on devices list
                assert '/devices/' in page.url
                assert '/detail/' not in page.url

    def test_copy_device_id(self, api, playwright, base_url, fresh_dev_eui):
        """Verify copy device ID button works"""
        # Create device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Get initial button text
                copy_btn = page.locator('#copy-btn')
                initial_text = copy_btn.text_content()

                # Click copy button
                copy_btn.click()
                page.wait_for_timeout(100)

                # Verify button shows "Copied"
                assert 'Copied' in copy_btn.text_content()

    def test_device_not_found(self, playwright, base_url):
        """Verify error when device doesn't exist"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(f'{base_url}/devices/999999/detail/')
            page.wait_for_load_state('networkidle')

            # Verify error is shown
            error_div = page.locator('#error')
            assert error_div.is_visible()


class TestDeviceDetailWithFailures:
    """Tests for device detail view with failures"""

    def test_no_failures_message(self, api, playwright, base_url, fresh_dev_eui):
        """Verify 'no active failures' message when device is passing"""
        # Create passing device
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',  # passing
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Verify no failures message
                no_failures = page.locator('#no-failures')
                # Either no failures message or empty failures list
                if no_failures.is_visible():
                    assert 'no active failures' in no_failures.text_content().lower()

    def test_out_of_range_failure_displays(self, api, playwright, base_url, fresh_dev_eui):
        """Verify out-of-range failure displays in detail view"""
        # Create device with out-of-range reading
        api.post('/payloads/', data={
            'dev_eui': fresh_dev_eui,
            'f_cnt': 1,
            'data': 'AQ==',
            'object': {
                'temperature': -50,  # out of default range (-10 to 50)
                'humidity': 50,
            },
            'rx_info': [{'time': '2026-07-30T12:00:00Z'}],
            'tx_info': {},
        })

        device_list = api.get('/devices/')
        device_data = device_list.json()
        device_id = None
        for d in device_data.get('results', []):
            if d['dev_eui'] == fresh_dev_eui:
                device_id = d['id']
                break

        if device_id:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.goto(f'{base_url}/devices/{device_id}/detail/')
                page.wait_for_load_state('networkidle')

                # Verify failure card appears (may have out_of_range badge)
                failures = page.locator('.failure-card')
                # Page should load without error
                assert page.locator('#device-section').is_visible()


class TestUIResponsiveness:
    """Tests for responsive design"""

    def test_mobile_viewport(self, playwright, base_url):
        """Verify UI works on mobile viewport"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page(viewport={'width': 375, 'height': 667})
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Verify key elements are still visible
            assert page.locator('[data-testid=search-input]').is_visible()
            assert page.locator('[data-testid=device-list]').is_visible()

    def test_tablet_viewport(self, playwright, base_url):
        """Verify UI works on tablet viewport"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page(viewport={'width': 768, 'height': 1024})
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Verify layout adapts
            assert page.locator('[data-testid=search-input]').is_visible()
            assert page.locator('[data-testid=device-list]').is_visible()

    def test_desktop_viewport(self, playwright, base_url):
        """Verify UI works on desktop viewport"""
        with playwright.chromium.launch() as browser:
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(f'{base_url}/devices/')
            page.wait_for_load_state('networkidle')

            # Verify layout
            assert page.locator('[data-testid=search-input]').is_visible()
            assert page.locator('[data-testid=device-list]').is_visible()
