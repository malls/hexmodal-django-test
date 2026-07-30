# HDT-16: Device Search/Filter UI

## Overview
Build a web-based UI for searching and filtering devices by health status and failure type. Displays device list with status indicators, failure counts, and links to device detail views. Powered by the HDT-15 API endpoints.

## Technology Stack
- **Frontend**: Vanilla JavaScript (no framework) + HTML5 + CSS3
- **Backend**: Django templates (single-page view with JS enhancement)
- **API**: Consumes DRF endpoints from HDT-15
- **Auth**: Token authentication via session or API token
- **Testing**: Playwright E2E tests

## Key Files to Create/Modify
- `telemetry/templates/devices_search.html` — Main search/list view template
- `telemetry/templates/device_detail.html` — Device detail view template
- `telemetry/static/js/devices-search.js` — Client-side logic for search/filter
- `telemetry/static/css/devices.css` — Styling (responsive, light/dark mode)
- `telemetry/views.py` — Add TemplateView for device pages
- `telemetry/urls.py` — Add URL patterns for views
- `e2e/test_devices_ui.py` — Playwright E2E tests

## UI Design

### Search/List View (`/devices/`)
```
┌─────────────────────────────────────────────────────────┐
│ Device Health Monitor                                   │
├─────────────────────────────────────────────────────────┤
│ Search: [______________]  Filter by Status:            │
│                           [✓] Passing [ ] Failing       │
│                           Filter by Failure:            │
│                           [ ] Inactivity                │
│                           [ ] Out of Range              │
│                           [✓] Frequency Anomaly         │
│                           [Apply Filters]               │
├─────────────────────────────────────────────────────────┤
│ Device ID       Status    Failures   Last Activity      │
├─────────────────────────────────────────────────────────┤
│ device1         ⚠ Failing 2         2 hours ago  >     │
│ device2         ✓ Passing  0         30 min ago   >     │
│ device3         ✓ Passing  1         5 min ago    >     │
│ device4         ⚠ Failing 3         12 hours ago >     │
├─────────────────────────────────────────────────────────┤
│ Showing 1-4 of 42 devices  [< Prev] [1] [2] [3] [Next >]
└─────────────────────────────────────────────────────────┘
```

### Device Detail View (`/devices/{id}/`)
```
┌─────────────────────────────────────────────────────────┐
│ Device: device1 (abcdabcdabcdabcd)                  [←] │
├─────────────────────────────────────────────────────────┤
│ Status: Failing           Created: 2026-07-15          │
│ Last Activity: 2 hours ago                             │
│ Latest Status: failing                                 │
├─────────────────────────────────────────────────────────┤
│ Active Failures:                                        │
│ ⚠ Inactivity                                           │
│   Last seen: 2 hours ago                               │
│   Threshold: 1 hour                                    │
│                                                         │
│ ⚠ Out of Range                                         │
│   Temperature: 35.2°C (range: 15-25°C)                │
│   Last seen: 30 minutes ago                            │
├─────────────────────────────────────────────────────────┤
│ Health Configuration:                                  │
│ • Inactivity Window: 1 hour                            │
│ • Temperature: 15-25°C                                 │
│ • Humidity: 30-70%                                     │
│ • Expected Frequency: 600 seconds                      │
└─────────────────────────────────────────────────────────┘
```

## Features

### 1. Search Box
- Search by device dev_eui (substring match via frontend filter)
- Real-time search as user types (no backend request needed for simple case)
- Clear button to reset search
- Placeholder: "Search by device ID..."

### 2. Filter Controls
**Status Filter** (radio or toggle)
- All (default)
- Passing only
- Failing only

**Failure Type Filter** (checkboxes)
- [ ] Inactivity
- [ ] Out of Range
- [ ] Frequency Anomaly
- "Show all" toggle to clear all

### 3. Device List Table
**Columns:**
- Device ID (dev_eui) — sortable, clickable
- Status — indicator (✓ passing / ⚠ failing / ? unknown)
- Failure Count — badge showing # of active failures
- Last Activity — relative time ("5 min ago", "2 hours ago")
- Action — "→" icon to detail view

**Sorting:**
- Click column header to sort (device ID, status, failure count, last activity)
- Visual indicator (▲ ▼) for sort direction
- Default: sorted by status (failing first) then by last activity

### 4. Device Detail View
**Header:**
- Device ID (dev_eui) with copy-to-clipboard button
- Back button/link to device list
- Status indicator with timestamp

**Sections:**
1. **Overview**
   - Status (Passing / Failing / Unknown)
   - Created date
   - Last activity (last payload created_at)
   - Latest reported status

2. **Active Failures**
   - List of current failures with type badges
   - For each failure:
     - Failure type (Inactivity / Out of Range / Frequency)
     - Specific details:
       - Inactivity: last seen time, threshold
       - Out of Range: readings and bounds
       - Frequency: gap time, expected frequency
     - Timestamp of failure

3. **Health Configuration**
   - Display-only card showing current thresholds
   - Inactivity Window (seconds)
   - Temperature range (min-max)
   - Humidity range (min-max)
   - Expected frequency (seconds)

### 5. Pagination
- Show 20 devices per page
- Prev/Next buttons
- Current page indicator: "Showing 1-20 of 150"
- Jump-to-page input (optional enhancement)

### 6. Empty States
- "No devices yet" when list is empty
- "No results match your search" when filters return nothing
- "This device has no active failures" in detail view

## API Integration

### Endpoints Used
1. **List**: `GET /api/payloads/devices/?failure_type=inactivity,out_of_range`
   - Query params: `failure_type`, `page`, `ordering`
   - Response includes: id, dev_eui, latest_status, failure_count, updated_at

2. **Detail**: `GET /api/payloads/devices/{id}/`
   - Response includes: id, dev_eui, latest_status, created_at, updated_at, failures (with details)

3. **Config**: `GET /api/payloads/health-configs/?device_id={id}`
   - Response includes: device, all config thresholds

### Error Handling
- 401 Unauthorized → Redirect to login
- 404 Not Found → Show "Device not found" page
- 500 Server Error → Show error banner with retry button
- Network timeout → Show "Failed to load. Retrying..." message

## Styling Guidelines

### Design Principles
- Clean, minimal, accessible
- Responsive (desktop, tablet, mobile)
- Support light and dark themes via CSS variables
- Use semantic HTML5
- Accessible color contrasts (WCAG AA)
- Clear visual hierarchy

### Color Scheme (CSS Variables)
```css
--color-passing: #10b981     /* green */
--color-failing: #ef4444     /* red */
--color-unknown: #6b7280     /* gray */
--color-badge-inactivity: #f59e0b    /* amber */
--color-badge-out-of-range: #ec4899  /* pink */
--color-badge-frequency: #8b5cf6     /* purple */

--bg-primary: #ffffff        /* light mode */
--bg-secondary: #f9fafb
--text-primary: #111827
--text-secondary: #6b7280

/* Dark mode overrides via @media (prefers-color-scheme: dark) */
```

### Responsive Breakpoints
- Mobile: < 640px (single column, simplified layout)
- Tablet: 640px - 1024px (two columns)
- Desktop: > 1024px (full layout with sidebar)

## Client-Side Logic (JavaScript)

### Key Functions
1. `fetchDeviceList(filters)` — GET /api/devices/ with filters
2. `fetchDeviceDetail(id)` — GET /api/devices/{id}/
3. `applyFilters()` — Update list based on filter controls
4. `handleSearch(query)` — Filter displayed list by dev_eui
5. `formatRelativeTime(timestamp)` — Convert to "5 min ago"
6. `updateSortOrder(column)` — Change sort direction
7. `navigateToDevice(id)` — Redirect to detail view
8. `copyToClipboard(text)` — Copy device ID

### Features
- Debounced search (300ms) to avoid excessive filtering
- Pagination handled server-side (link to prev/next pages)
- Relative time updates every 30 seconds
- Loading spinners while fetching data
- Error messages with retry buttons
- No page reload on filter/search changes (AJAX)

## E2E Testing (Playwright)

### Test Coverage
1. **Search View**
   - Load page, verify device list renders
   - Search by dev_eui substring, list filters
   - Filter by status (Passing, Failing)
   - Filter by failure type (Inactivity, Out of Range, Frequency)
   - Pagination (click next, verify new page loaded)
   - Click device row, navigate to detail

2. **Detail View**
   - Load device detail, verify all sections display
   - Verify failure cards display with correct details
   - Verify health config displays thresholds
   - Back button returns to list
   - Copy dev_eui to clipboard works
   - Device not found (404) shows error message

3. **Cross-Platform**
   - Test on desktop (1920x1080), tablet (768x1024), mobile (375x667)
   - Dark mode rendering
   - Keyboard navigation (tab through filters, links)
   - Screen reader compatibility (semantic HTML, labels)

### Test Scenarios (Example)
```python
async def test_search_and_filter_devices(page):
    await page.goto('/devices/')
    
    # Verify list loads
    await expect(page.locator('[data-testid=device-list]')).to_be_visible()
    
    # Search by dev_eui
    await page.fill('[data-testid=search-input]', 'device1')
    await page.wait_for_timeout(300)  # debounce
    rows = await page.locator('[data-testid=device-row]').all()
    assert len(rows) == 1
    
    # Filter by failing status
    await page.click('[data-testid=status-failing]')
    rows = await page.locator('[data-testid=device-row]').all()
    assert all(row has failing status)
    
    # Filter by failure type
    await page.click('[data-testid=failure-type-inactivity]')
    rows = await page.locator('[data-testid=device-row]').all()
    assert all(row has inactivity failure)
    
    # Click device row
    await page.click('[data-testid=device-row]', first=True)
    await expect(page).to_have_url('/devices/*/detail/')
```

## Acceptance Criteria

### Functionality
1. ✓ Device list displays all devices from API
2. ✓ Search by dev_eui filters list in real-time
3. ✓ Status filter (All/Passing/Failing) works correctly
4. ✓ Failure type filter (checkboxes) work correctly
5. ✓ Pagination: prev/next navigate pages correctly
6. ✓ Device detail view displays all information
7. ✓ Active failures display with correct details
8. ✓ Health config displays current thresholds
9. ✓ Back button/link returns to list
10. ✓ Sorting by device ID, status, failure count works

### UI/UX
1. ✓ Responsive layout on mobile/tablet/desktop
2. ✓ Light and dark mode rendering
3. ✓ Clear visual hierarchy and status indicators
4. ✓ Loading states while fetching data
5. ✓ Error messages with retry capability
6. ✓ Accessible: WCAG AA colors, semantic HTML

### Testing
1. ✓ E2E tests for search, filter, pagination, detail
2. ✓ Tests pass on desktop, tablet, mobile viewports
3. ✓ Tests pass in light and dark modes
4. ✓ Tests verify API calls are made with correct params
5. ✓ Tests verify error handling (404, 500, timeout)

### Performance
1. ✓ Page loads in < 2 seconds on slow 4G
2. ✓ Debounced search (no lag on typing)
3. ✓ Smooth relative time updates (no jank)

## Dependencies
- Depends on: HDT-15 (Device Status API)
- Requires: DRF API endpoints working with filters
- Test dependency: Playwright with Django test utilities

## Future Enhancements (Not in Scope)
- Export device list to CSV
- Bulk actions (resolve all failures for selected devices)
- Historical failure graphs
- Alert notifications on status change
- Admin panel to manage device config
- Real-time WebSocket updates (for live dashboard)
- Advanced filtering (date range, config values)
