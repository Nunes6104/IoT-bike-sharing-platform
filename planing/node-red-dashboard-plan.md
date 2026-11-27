# Dashboard enhancement plan

## Problem and approach

Enhance the existing authenticated Node-RED dashboard with accessible loading states, charts, automatic near-real-time updates, a station-availability map page, and English/Portuguese (Portugal) translations. Keep the five-service architecture and current analytics/business rules. This is a dashboard-focused increment, not a framework rewrite or implementation of all remaining Stage 2 features.

## Inspected current state

- `dashboard/flows.json` embeds one HTML page at `/bike-sharing`, with tables/cards, a text loading message, and a manual Update dashboard button. It proxies the authenticated processor analytics API through verified HTTPS.
- `dashboard/settings.js` protects HTTP flows and the editor, configures browser-facing HTTPS, and keeps the analytics token server-side.
- `processor/api.py` currently serves only analytics and health endpoints. `processor/analytics.py` already returns all requested chart metrics, using half-open date ranges limited to 31 days, source UTC-04:00 time, and Monday weekly boundaries.
- The analytics implementation currently reads all completed-trip payloads before filtering. Repeated polling must be measured against the real dataset rather than assumed inexpensive.
- Actual station reference records contain `station_id`, `name`, `lat`, `lon`, `capacity`, and `city`. Actual status events include available bikes, e-bikes, disabled bikes/docks, available docks, and installation/rental/return flags.
- The supplied dataset documentation explicitly states that e-bikes are included in total available bikes and that status updates are emitted when state changes. Do not double-count e-bikes or claim an older report proves a station is unavailable.
- Existing API and aggregation tests use isolated SQLite databases. Compose uses MySQL and Node-RED, with the dashboard image currently having no project-specific frontend build.
- The worktree was clean at inspection. No repository files have been changed for this plan.

## Confirmed scope and decisions

- Map means station locations with reported bike availability, not individual bicycle tracking.
- Include charts for member/casual trip trends, energy/fare trends, average/total duration, time-of-day distribution, and station demand/empty-full observations.
- Automatically poll every five seconds. This is near-real-time polling, not instantaneous server push. Updates apply only to committed database data.
- Show a loading view on initial fetch. Keep the last successful content visible with an updating indicator during subsequent requests, including filter changes.
- Map uses the latest committed station reports, independently of the analytics date filters.
- Use OpenStreetMap street tiles over HTTPS, with required attribution. This needs internet and exposes the viewport/IP to the tile provider; no credentials or private application payloads are sent.
- Initial language is English; a saved user selection takes precedence. Support `en` and `pt-PT`, with an immediate language toggle and no page refresh.
- All user-facing dates/times use `dd/mm/yyyy hh:mm`, with 24-hour time in both languages. Keep source UTC-04:00 explicit and retain machine-readable ISO timestamps in API contracts.
- Existing analytics filters remain fixed until the operator changes them; polling does not move the selected historical date range.

## Implementation todos

### 1. Establish a shared dashboard shell and explicit UI state

Keep Node-RED as the web entry point and authenticated HTTPS API proxy. Reuse one application shell for `/bike-sharing` and `/bike-sharing/map`, with analytics/map navigation and shared language, loading, and connection indicators.

Extract the embedded JavaScript/CSS into small frontend assets under `dashboard/public/` so charts, translations, state, and map logic are maintainable. Serve only explicit allowlisted asset paths through authenticated Node-RED HTTP flows; do not expose arbitrary filesystem paths or secrets.

Use browser history navigation without a full document refresh, including back/forward handling and direct access to the map URL. Preserve the analytics payload/filters and map center, zoom, and selected station across navigation and language changes.

Model initial loading, background updating, ready, empty, and error states explicitly. On failure, retain previous content, identify it as last successfully fetched data, and show an accessible error message. Provide automatic recovery and distinct authentication/validation failures; never replace failures with zero-valued data.

### 2. Add a latest-station snapshot API and secure map proxy

Add a focused station snapshot service and authenticated processor endpoint `/api/stations/latest`, plus a same-origin Node-RED proxy with a fixed upstream target. Keep the existing analytics response compatible.

Return every reference station, coordinates/capacity/city, its latest committed non-rejected status (ordered by source timestamp, then sequence as a deterministic tie-breaker), report time/sequence, availability fields, operational flags, and validation warnings. Use explicit null status for stations with no observations.

Include snapshot fetch time and latest committed dataset event time as separate metadata. Historical replay is not wall-clock telemetry: show March 2024 report times accurately. Reject unsupported/repeated query parameters consistently with the current API.

Do not sum e-bikes twice, invent bike positions, estimate availability from trips, treat missing reports as zero, or silently clamp anomalous values. Missing/invalid coordinates are reported as unmappable; the station remains available in an accessible list. Older reports remain labeled "last reported", not asserted to be current physical truth.

Read one coherent committed snapshot per response; do not depend on MQTT publisher acknowledgment as proof of persistence. Keep TLS verification, browser authentication, and server-only service tokens unchanged.

### 3. Implement coordinated automatic refresh

Remove the manual update button. Load immediately, then schedule the next request five seconds after the preceding request completes, avoiding overlapping polls. Fetch analytics only when its page is active and station snapshots only when the map is active.

Apply valid filter changes automatically after a short debounce; preserve existing half-open range, 31-day bound, and source-time semantics. Incomplete or invalid edits show local validation errors rather than requests with invented values.

Use cancellation/generation guards so slow old responses cannot overwrite newer filters or page state. Bound request timeouts, stop timers/requests on disposal, and pause polling when the tab is hidden; refresh immediately when visible again. Language changes must not trigger a data reload.

Retry transient failures with bounded backoff and a visible status; resume five-second scheduling after recovery. Distinguish invalid filters and authentication failures from transient service/network errors.

Measure response/query/render times with the supplied dataset before choosing any optimization. Do not add a background scheduler, shared cache, or schema migration unless measurements show it is required. If necessary, improve only the directly affected query or introduce a bounded freshness-preserving optimization with invalidation tests.

### 4. Add charts without changing metric definitions

Use responsive SVG charts to avoid a new chart framework. Keep existing tables or accessible equivalent data views alongside graphics.

- Member/casual completed trips: stacked bars by selected hourly/daily/weekly bucket.
- Known e-bike energy and estimated fare: separate plots with explicit kWh/USD units; retain unknown-energy counts and coverage.
- Average and total duration: distinct series/panels with minutes/hours clearly labeled and unknown averages preserved.
- Time of day: distribution bars for the existing four source-local periods.
- Station demand: member/casual departures/arrivals, plus observed empty/full shares with observation counts. Rank the chart for readability while retaining all stations in the detailed table; identify any chart subset explicitly.

Use labels, legends, accessible summaries, and tooltips. Do not mix incomparable units on an unlabeled axis or convert unknown values into zero. Charts/tables render from the same successful payload.

### 5. Add the station map page and reproducible map assets

Use Leaflet for street-map interaction because the current dashboard has no map component and plain SVG does not provide street tiles/pan/zoom. Keep Leaflet JavaScript/CSS/images local: add a minimal dashboard dependency manifest/lockfile and a Dockerfile based on the current Node-RED image, installing/copying assets during image build.

Update Compose only for the dashboard build and required read-only frontend asset mounts. Do not change MQTT, database, or ML responsibilities.

Show station markers and an accessible station list. A station detail displays name/ID, capacity, total available bikes, the included e-bike count, docks, disabled counts, operational flags, last report time, and warnings. Distinguish unknown status, empty, full, and reported availability using text as well as color.

Update marker/list data in place, preserving zoom/center/selection. Fit the station extent on initial map creation only. Show an explicit "latest reports, independent of analytics filters" label.

Retain attribution and obey the tile provider's usage policy. Avoid bulk tile downloads, prefetching, or offline tile caching. If tiles fail, show a visible map-background error and keep the station list/data usable rather than hiding the failure.

### 6. Add language switching and exact date/time presentation

Use one shared `en`/`pt-PT` translation dictionary for headings, controls, charts, table headers, map details, loading/error/empty states, accessibility labels, and status messages. Preserve proper station names and USD currency; translate labels, not identifiers or money assumptions.

Keep raw payloads and active state separate from rendering. The language toggle updates labels, document language/title, chart text, and map popups in place without fetching, refreshing the page, clearing filters, losing map position, or dismissing the selected station.

Persist only language preference locally, not authentication data. If browser storage is unavailable, retain switching for the current session without breaking the page.

Implement a shared exact date/time formatter and strict filter parser so neither browser locale nor the operator's operating-system timezone changes the requested format. Avoid depending on native `datetime-local` presentation, which cannot guarantee `dd/mm/yyyy hh:mm` across browsers. Show hour/day/week bucket starts consistently; identify bucket granularity and exclusive end boundaries explicitly. API timestamps remain ISO with explicit offsets.

### 7. Verify and document the increment

Extend existing API/analytics tests and add focused snapshot tests for latest status selection, equal-timestamp ordering, out-of-order commits, missing reports/coordinates, warning-bearing statuses, total/e-bike semantics, authorization, and failures. Preserve existing aggregation tests.

Add focused frontend/browser checks for delayed requests, empty results, filter races, failure/recovery, automatic refresh without a button, page navigation, language switching without reload, exact date formatting, and map updates preserving view state.

Run the smallest relevant Python test selectors and the full existing suite only if targeted results indicate wider risk. Use a lightweight JavaScript test runner for pure state/formatting functions if the extracted frontend permits it; use browser tests for actual visible behaviour.

Verify with an isolated Compose project and disposable volumes where available: real MySQL snapshot reads, authenticated HTTPS proxies, local map assets, a short committed Stage 2 replay appearing automatically in analytics/map, and representative full-dataset request/render timing. Do not reset existing database volumes or replay checkpoints. Report any unavailable Docker/browser/network prerequisites honestly.

Update root, dashboard, processor, and tests READMEs with routes, build/run/test commands, polling timing, loading behaviour, map data-time scope, OpenStreetMap dependency/privacy/attribution, languages, and date formatting. Describe only verified capabilities.

## Likely files

- `dashboard/flows.json`, `dashboard/settings.js` only if serving assets requires settings changes, `dashboard/README.md`
- New `dashboard/public/` application assets, `dashboard/Dockerfile`, `dashboard/package.json`, and its generated lockfile
- `docker-compose.yml` for the dashboard image/assets only
- `processor/api.py`, new `processor/station_snapshot.py`, `processor/analytics.py` only for demonstrated polling-related needs, `processor/README.md`
- `tests/test_api.py`, existing `tests/test_analytics.py` if aggregation changes, new focused snapshot/frontend/browser tests, `tests/README.md`
- Root `README.md`
- No database migration planned unless measured query needs justify one

## Dependencies

- Shared UI shell precedes automatic refresh, charts, map frontend, and localization.
- Snapshot API precedes map frontend.
- Frontend map assets may be prepared independently of snapshot implementation.
- Verification/documentation depends on all requested behaviour being implemented.

## Acceptance criteria

1. Initial async fetch displays an accessible loading state until data is rendered. Subsequent requests retain prior content and show a non-blocking updating indicator; failures are explicit.
2. All five confirmed chart groups reflect the existing API values and units. Tables/accessible alternatives retain data coverage and unknown-value distinctions.
3. `/bike-sharing/map` opens directly and through in-app navigation; every mappable reference station is represented, and stations without status display unknown rather than zero.
4. After a completed response, the next normal poll starts five seconds later. A commit made after that response appears by completion/render of the next successful poll; record measured request/render latency separately. No overlapping requests or stale-response overwrites occur. There is no manual update button.
5. Analytics keeps selected filters; map always shows latest committed reports. Older historical reports are not presented as fresh wall-clock observations.
6. EN/PT-PT switching performs no document reload or data request and preserves data, filters, current page, map viewport, and selected station.
7. All visible dates/times, including editable filters, table buckets, report times, and fetch times, use `dd/mm/yyyy hh:mm` with explicit timezone context; English does not switch to month-first dates.
8. TLS/authentication remain enforced, service tokens never reach the browser, frontend dependencies are reproducible/local, and third-party tiles remain HTTPS with attribution.
9. Validation is actually executed and documented; any unverified integration or performance claim is clearly identified.

## Boundaries and considerations

- Excluded: individual bike GPS/location tracking, active-trip UI, clustering/evolution, anomaly detection, rebalancing recommendations, tariff changes, report/submission work, and a dashboard framework migration.
- No arbitrary stale-time cutoff is introduced: status messages are change-driven, not periodic heartbeats. Report age/time is visible without claiming lack of a report proves missing bikes.
- OpenStreetMap availability is an external dependency. Coordinate-only/list functionality must remain usable when its tiles cannot load.
- Five seconds is the selected polling delay, not a promise of instantaneous delivery or a fixed end-to-end latency under failures.
