/**
 * Device Search/Filter UI
 * Handles device list display, search, filtering, pagination via API
 */

const API_BASE = '/api/payloads';
const PAGE_SIZE = 20;
let debounceTimer = null;
let currentPage = 1;
let totalCount = 0;
let currentFilters = {
    search: '',
    status: '',
    failure_type: [],
    ordering: 'dev_eui',
};

// Detect if we're on search page or detail page
const isDetailPage = typeof deviceId !== 'undefined';

/**
 * Debounce function - delays callback execution
 */
function debounce(fn, delay) {
    return function(...args) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => fn(...args), delay);
    };
}

/**
 * Format relative time (e.g., "5 min ago", "2 hours ago")
 */
function formatRelativeTime(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now - time;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return 'just now';
    if (diffMinutes < 60) return `${diffMinutes} min${diffMinutes > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

    const options = { month: 'short', day: 'numeric' };
    if (time.getFullYear() !== now.getFullYear()) {
        options.year = 'numeric';
    }
    return time.toLocaleDateString('en-US', options);
}

/**
 * Format date (e.g., "Jul 15, 2026")
 */
function formatDate(timestamp) {
    const date = new Date(timestamp);
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copy-btn');
        const originalText = btn.textContent;
        btn.textContent = '✓ Copied';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    });
}

/**
 * Build query parameters from filters
 */
function buildQueryParams() {
    const params = new URLSearchParams();

    if (currentFilters.search) {
        params.append('search', currentFilters.search);
    }
    if (currentFilters.status) {
        params.append('status', currentFilters.status);
    }
    if (currentFilters.failure_type.length > 0) {
        params.append('failure_type', currentFilters.failure_type.join(','));
    }
    if (currentFilters.ordering) {
        params.append('ordering', currentFilters.ordering);
    }
    if (currentPage > 1) {
        params.append('page', currentPage);
    }

    return params.toString();
}

/**
 * Update URL query params without reloading
 */
function updateURL() {
    const query = buildQueryParams();
    const newURL = query ? `?${query}` : '';
    window.history.replaceState({}, '', newURL);
}

/**
 * Fetch device list from API
 */
async function fetchDeviceList() {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const listSection = document.getElementById('device-list-section');

    if (loading) loading.classList.remove('hidden');
    if (error) error.classList.add('hidden');
    if (listSection) listSection.classList.add('hidden');

    try {
        const query = buildQueryParams();
        const url = query ? `${API_BASE}/devices/?${query}` : `${API_BASE}/devices/`;

        const response = await fetch(url, {
            credentials: 'include'  // Send session cookie
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (loading) loading.classList.add('hidden');
        if (listSection) listSection.classList.remove('hidden');

        renderDeviceList(data);
        updateURL();
    } catch (err) {
        if (loading) loading.classList.add('hidden');
        if (error) {
            error.classList.remove('hidden');
            document.getElementById('error-message').textContent =
                `Failed to load devices: ${err.message}`;
        }
        console.error('Error fetching devices:', err);
    }
}

/**
 * Render device list table
 */
function renderDeviceList(data) {
    const tbody = document.getElementById('device-table-body');
    const emptyState = document.getElementById('empty-state');
    const pageStart = document.getElementById('page-start');
    const pageEnd = document.getElementById('page-end');
    const totalCountEl = document.getElementById('total-count');
    const pageInfo = document.getElementById('page-info');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    totalCount = data.count;
    totalCountEl.textContent = totalCount;

    if (!data.results || data.results.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        return;
    }

    emptyState.classList.add('hidden');

    // Calculate pagination info
    const start = (currentPage - 1) * PAGE_SIZE + 1;
    const end = Math.min(currentPage * PAGE_SIZE, totalCount);
    pageStart.textContent = start;
    pageEnd.textContent = end;
    pageInfo.textContent = `Page ${currentPage}`;

    // Enable/disable pagination buttons
    prevBtn.disabled = !data.previous;
    nextBtn.disabled = !data.next;

    // Render rows
    tbody.innerHTML = data.results.map(device => {
        const statusClass = device.latest_status === 'passing' ? 'passing' :
                           device.latest_status === 'failing' ? 'failing' : 'unknown';
        const statusEmoji = statusClass === 'passing' ? '✓' :
                           statusClass === 'failing' ? '⚠' : '?';

        return `
            <tr data-testid="device-row">
                <td>
                    <span class="device-id">${escapeHtml(device.dev_eui)}</span>
                </td>
                <td>
                    <span class="status-indicator status-${statusClass}">
                        ${statusEmoji} ${device.latest_status}
                    </span>
                </td>
                <td>
                    <span class="failure-count ${device.failure_count === 0 ? 'zero' : ''}">
                        ${device.failure_count}
                    </span>
                </td>
                <td>
                    <span class="relative-time">${formatRelativeTime(device.updated_at)}</span>
                </td>
                <td class="row-action">
                    <span class="detail-link" onclick="goToDetail(${device.id})">→</span>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Navigate to device detail page
 */
function goToDetail(deviceId) {
    window.location.href = `/devices/${deviceId}/detail/`;
}

/**
 * Handle search input change (debounced)
 */
const handleSearch = debounce(function(query) {
    currentFilters.search = query;
    currentPage = 1;
    fetchDeviceList();
}, 300);

/**
 * Handle status filter change
 */
function handleStatusFilter(event) {
    currentFilters.status = event.target.value;
    currentPage = 1;
    fetchDeviceList();
}

/**
 * Handle failure type filter change
 */
function handleFailureTypeFilter() {
    const checkboxes = document.querySelectorAll('input[name="failure_type"]:checked');
    currentFilters.failure_type = Array.from(checkboxes).map(cb => cb.value);
    currentPage = 1;
    fetchDeviceList();
}

/**
 * Clear search and filters
 */
function clearFilters() {
    document.getElementById('search-input').value = '';
    document.querySelectorAll('input[name="status"]').forEach(cb => {
        if (cb.value === '') cb.checked = true;
        else cb.checked = false;
    });
    document.querySelectorAll('input[name="failure_type"]').forEach(cb => {
        cb.checked = false;
    });
    currentFilters.search = '';
    currentFilters.status = '';
    currentFilters.failure_type = [];
    currentPage = 1;
    fetchDeviceList();
}

/**
 * Handle sorting
 */
function handleSort(column) {
    if (currentFilters.ordering === column) {
        // Toggle descending
        currentFilters.ordering = `-${column}`;
    } else if (currentFilters.ordering === `-${column}`) {
        // Reset to ascending
        currentFilters.ordering = column;
    } else {
        currentFilters.ordering = column;
    }
    currentPage = 1;
    fetchDeviceList();
}

/**
 * Handle pagination
 */
function goToPage(pageNum) {
    currentPage = pageNum;
    fetchDeviceList();
}

/**
 * Initialize search page
 */
function initSearchPage() {
    const searchInput = document.getElementById('search-input');
    const clearBtn = document.getElementById('clear-search');
    const clearFiltersBtn = document.getElementById('clear-filters');
    const statusRadios = document.querySelectorAll('input[name="status"]');
    const failureCheckboxes = document.querySelectorAll('input[name="failure_type"]');
    const sortBtns = document.querySelectorAll('.sort-btn');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const retryBtn = document.querySelector('.retry-btn');

    // Event listeners
    searchInput.addEventListener('input', (e) => {
        handleSearch(e.target.value);
    });

    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        currentFilters.search = '';
        currentPage = 1;
        fetchDeviceList();
    });

    clearFiltersBtn.addEventListener('click', clearFilters);

    statusRadios.forEach(radio => {
        radio.addEventListener('change', handleStatusFilter);
    });

    failureCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', handleFailureTypeFilter);
    });

    sortBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            handleSort(btn.dataset.column);
            updateSortIndicators();
        });
    });

    prevBtn.addEventListener('click', () => {
        if (currentPage > 1) goToPage(currentPage - 1);
    });

    nextBtn.addEventListener('click', () => {
        goToPage(currentPage + 1);
    });

    if (retryBtn) {
        retryBtn.addEventListener('click', fetchDeviceList);
    }

    // Load initial data
    fetchDeviceList();
}

/**
 * Update sort button indicators
 */
function updateSortIndicators() {
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.classList.remove('active');
        const indicator = btn.querySelector('.sort-indicator');
        if (currentFilters.ordering.startsWith('-')) {
            if (`-${btn.dataset.column}` === currentFilters.ordering) {
                btn.classList.add('active');
                indicator.textContent = '▼';
            }
        } else {
            if (btn.dataset.column === currentFilters.ordering) {
                btn.classList.add('active');
                indicator.textContent = '▲';
            }
        }
    });
}

/**
 * Fetch device detail from API
 */
async function fetchDeviceDetail(devId) {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const section = document.getElementById('device-section');

    if (loading) loading.classList.remove('hidden');
    if (error) error.classList.add('hidden');
    if (section) section.classList.add('hidden');

    try {
        // Fetch device
        const deviceResp = await fetch(`${API_BASE}/devices/${devId}/`, {
            credentials: 'include'
        });
        if (!deviceResp.ok) {
            throw new Error(`Device not found (${deviceResp.status})`);
        }
        const device = await deviceResp.json();

        // Fetch config
        const configResp = await fetch(`${API_BASE}/health-configs/?device_id=${devId}`, {
            credentials: 'include'
        });
        const configData = configResp.ok ? await configResp.json() : { results: [] };
        const config = configData.results?.[0];

        if (loading) loading.classList.add('hidden');
        if (section) section.classList.remove('hidden');

        renderDeviceDetail(device, config);
    } catch (err) {
        if (loading) loading.classList.add('hidden');
        if (error) {
            error.classList.remove('hidden');
            document.getElementById('error-message').textContent = `Error: ${err.message}`;
        }
        console.error('Error fetching device:', err);
    }
}

/**
 * Render device detail page
 */
function renderDeviceDetail(device, config) {
    const title = document.getElementById('device-title');
    const name = document.getElementById('device-name');
    const idEl = document.getElementById('device-id');
    const badge = document.getElementById('status-badge');
    const statusText = document.getElementById('status-text');
    const createdDate = document.getElementById('created-date');
    const lastActivity = document.getElementById('last-activity');
    const latestStatus = document.getElementById('latest-status');

    // Header
    title.textContent = `Device: ${device.dev_eui}`;
    name.textContent = device.dev_eui;
    idEl.textContent = device.dev_eui;

    // Status badge
    badge.textContent = device.latest_status.charAt(0).toUpperCase() + device.latest_status.slice(1);
    badge.className = `status-badge ${device.latest_status}`;

    // Overview
    statusText.textContent = device.latest_status.charAt(0).toUpperCase() + device.latest_status.slice(1);
    createdDate.textContent = formatDate(device.created_at);
    lastActivity.textContent = formatRelativeTime(device.updated_at);
    latestStatus.textContent = device.latest_status;

    // Failures
    renderFailures(device.failures);

    // Config
    renderConfig(config);

    // Copy button
    const copyBtn = document.getElementById('copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => copyToClipboard(device.dev_eui));
    }
}

/**
 * Render active failures
 */
function renderFailures(failures) {
    const list = document.getElementById('failures-list');
    const noFailures = document.getElementById('no-failures');

    const activeFailures = failures.filter(f => f.resolved_at === null);

    if (activeFailures.length === 0) {
        list.innerHTML = '';
        noFailures.classList.remove('hidden');
        return;
    }

    noFailures.classList.add('hidden');

    list.innerHTML = activeFailures.map(failure => {
        let details = '';

        if (failure.failure_type === 'payload_failing') {
            const hex = failure.details.decoded_hex;
            const fCnt = failure.details.f_cnt;
            details = `
                <div class="failure-detail-line">
                    <span>Value:</span>
                    <span>${hex} (not 1)</span>
                </div>
                <div class="failure-detail-line">
                    <span>Frame Count:</span>
                    <span>${fCnt}</span>
                </div>
            `;
        } else if (failure.failure_type === 'inactivity') {
            const lastPayload = failure.details.last_payload_time;
            details = `
                <div class="failure-detail-line">
                    <span>Last seen:</span>
                    <span>${lastPayload ? formatRelativeTime(lastPayload) : 'Never'}</span>
                </div>
                <div class="failure-detail-line">
                    <span>Threshold:</span>
                    <span>${Math.round(failure.details.inactivity_window_seconds / 60)} minutes</span>
                </div>
            `;
        } else if (failure.failure_type === 'out_of_range') {
            const temp = failure.details.temperature !== null ? failure.details.temperature : '-';
            const humidity = failure.details.humidity !== null ? failure.details.humidity : '-';
            const config = failure.details.config;
            details = `
                <div class="failure-detail-line">
                    <span>Temperature:</span>
                    <span>${temp}°C (range: ${config.temp_min}–${config.temp_max}°C)</span>
                </div>
                <div class="failure-detail-line">
                    <span>Humidity:</span>
                    <span>${humidity}% (range: ${config.humidity_min}–${config.humidity_max}%)</span>
                </div>
            `;
        } else if (failure.failure_type === 'frequency_anomaly') {
            const gap = Math.round(failure.details.gap_seconds);
            const expected = failure.details.expected_frequency_seconds;
            details = `
                <div class="failure-detail-line">
                    <span>Gap:</span>
                    <span>${gap}s (expected: ${expected}s)</span>
                </div>
                <div class="failure-detail-line">
                    <span>Threshold:</span>
                    <span>${Math.round(failure.details.threshold_seconds)}s (1.5x)</span>
                </div>
            `;
        }

        return `
            <div class="failure-card ${failure.failure_type}">
                <span class="failure-type ${failure.failure_type}">
                    ${failure.failure_type.replace('_', ' ').toUpperCase()}
                </span>
                <div class="failure-details">
                    ${details}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render health configuration
 */
function renderConfig(config) {
    const inactivity = document.getElementById('config-inactivity');
    const temp = document.getElementById('config-temp');
    const humidity = document.getElementById('config-humidity');
    const frequency = document.getElementById('config-frequency');

    if (!config) {
        inactivity.textContent = '-';
        temp.textContent = '-';
        humidity.textContent = '-';
        frequency.textContent = '-';
        return;
    }

    inactivity.textContent = `${Math.round(config.inactivity_window_seconds / 60)} minutes`;
    temp.textContent = `${config.temp_min}–${config.temp_max}°C`;
    humidity.textContent = `${config.humidity_min}–${config.humidity_max}%`;
    frequency.textContent = `${config.expected_frequency_seconds} seconds`;
}

/**
 * Initialize detail page
 */
function initDetailPage() {
    if (typeof deviceId === 'undefined' || !deviceId) {
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('error-message').textContent = 'Invalid device ID';
        return;
    }
    fetchDeviceDetail(deviceId);
}

/**
 * Main initialization
 */
function init() {
    if (isDetailPage) {
        initDetailPage();
    } else {
        initSearchPage();
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
