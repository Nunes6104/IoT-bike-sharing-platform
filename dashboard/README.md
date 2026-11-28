# Dashboard

The authenticated Node-RED service is the browser entry point for the operator dashboard. It serves the analytics page at `https://localhost:1880/bike-sharing`, the station map at `/bike-sharing/map`, locally built frontend assets, and same-origin proxies to the processor. Both the Node-RED editor and HTTP flows retain HTTPS and basic authentication.

## Pages and behavior

- **Analytics** combines the fixed Stage 1 offline baseline with Stage 2 events received through MQTT. It offers native calendar and time filters interpreted in the source timezone (UTC−04:00), hourly/daily/Monday-weekly buckets, and refreshes as replayed events arrive. Filters are limited to 2024, the supplied dataset's year; update the bounds if datasets from other years are added. The exclusive end must be at least one minute after the start; moving the start past the end adjusts the end. Manually entered values outside these limits are rejected. Periods are limited to 31 days. The browser determines the calendar input display format.
- **Station map** displays reference station locations and the latest committed status from the fixed Stage 1 baseline plus Stage 2 events received through MQTT. It is independent of analytics filters and does not infer a status from trips or missing updates. The station list and details remain usable without map tiles.
- **Active trips** on the station map shows Stage 2 MQTT starts received so far without a later matching end, refreshing with the station snapshot. It uses source sequence and `ride_id`; historical replay times and incomplete source records mean an open trip is not a guarantee of a present-day rider.
- **Station profiles** shows the fixed Stage 1 model and baseline profiles plus Stage 2 cluster assignments recomputed from MQTT events received so far. The profile page refreshes every 30 seconds; the ML service refreshes online profiles every 60 seconds by default. Dedicated local-date controls select a 1–31 day range in the supplied period; the end date is exclusive.
- Analytics and map pages poll only while active, five seconds after each completed request. Polling pauses while the browser tab is hidden. Background refreshes retain last successful results, show failures explicitly, and retry transient failures with bounded backoff.
- The connection status reports browser-observed request/JSON and DOM/SVG render durations separately.
- The English and Portuguese (Portugal) language toggle updates labels without reloading or fetching data. Only the language preference is stored locally.

Displayed results use the fixed source UTC−04:00 offset and `dd/mm/yyyy hh:mm`; native date/time input formatting depends on the browser. API timestamps retain explicit ISO offsets. The dashboard does not display live bicycle positions or claim that historical reports describe current physical availability.

## Charts and data

Responsive SVG charts show member/casual trip trends, known e-bike energy, estimated fare, average and total duration, time-of-day counts, station demand, and observed empty/full update shares. Detailed trend and station tables remain available alongside the charts. Missing energy and unobserved station reports remain unknown, not zero. Energy, fare, and aggregation rules are owned by the processor.

The Leaflet library is installed from the pinned dashboard dependency lockfile and served locally. OpenStreetMap street tiles are fetched over HTTPS and attributed on the map. Tile requests reveal the browser IP and map viewport to the tile provider; no application payload or service credentials are sent to it. Internet access is required for street tiles.

One measured local in-memory SQLite run loaded the supplied 53,724 Stage 1 events, then took 1.814 seconds for analytics aggregation and 0.282 seconds to read and assemble an 83-station snapshot. These are local processor-service timings, not MySQL or end-to-end HTTPS measurements; the dashboard displays actual request and render timings at runtime. No query cache was added based on this single local measurement.

## Run and test

The root setup builds the dashboard image as part of Compose:

```powershell
docker compose up -d --build --wait
```

Open `https://localhost:1880/bike-sharing` and authenticate with user `admin`; the generated password is stored in `.local/dashboard/admin.password`. Trust `.local/certs/ca.crt` in the browser for the local development certificate.

Run the dependency-free frontend logic tests with Node.js:

```powershell
npm --prefix dashboard ci
npm --prefix dashboard test
```

Node-RED serves only the fixed allowlisted assets in its HTTP flows. It proxies `/api/analytics`, `/api/stations/latest`, and the authenticated `/api/ml/*` routes to fixed processor HTTPS endpoints and keeps the bearer token server-side. The profile tables show station/day feature data; missing distances and unobserved occupancy remain unknown.
