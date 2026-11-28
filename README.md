# Bike-Sharing IoT Platform

Docker Compose project for the supplied Jersey City and Hoboken bike-share dataset. It includes a MySQL database, TLS-enabled Mosquitto broker, Python event processor, dedicated station-profiling service, online replay publisher, and Node-RED operator dashboard.

## Current functionality

- Loads station reference data and Stage 1 JSONL events into MySQL.
- Keeps Stage 1 as an immutable offline baseline and stores Stage 2 MQTT events separately with duplicate protection and quarantine for rejected payloads.
- Replays Stage 2 JSONL events through MQTT with configurable timing and an acknowledgment-based checkpoint.
- Serves a date-filtered dashboard with trip, energy, fare, duration, time-of-day, and station-demand charts and detailed tables.
- Shows a station availability map with the latest committed status reports and unknown status for stations without observations.
- Shows Stage 2 trip starts with no later matching end on the station map, refreshed with the latest station snapshot.
- Trains a versioned unsupervised station-profile model from Stage 1 and refreshes Stage 2 daily cluster assignments and explainable operational flags.
- Combines the fixed Stage 1 baseline with only the Stage 2 records received through MQTT for dashboard analytics, station status, active trips, and online ML profiles.
- Uses TLS for MQTT on port **1883**, MySQL connections, and the dashboard-to-processor API. Port 1883 is explicitly configured as TLS, not plaintext.

The dashboard reports completed trips from `trip_ended` events, grouped by source-local trip start time. Its end date is exclusive. Energy coverage is shown explicitly when coordinates are unavailable; missing station updates are not interpreted as zero bikes or docks. The map shows committed reports, not live bike positions or guaranteed present-day availability. Its Stage 2 open-trip table shows trip starts with no later matching end in the replay stream; historical replay timestamps and incomplete source records mean these are not guaranteed present-day riders. The profile page presents station/day cluster assignments and rule-based flags; it does not provide rebalancing recommendations.

## Repository map

| Folder | Purpose |
|---|---|
| [processor/](processor/README.md) | Validation, persistence, MQTT subscriber, analytics API |
| [publisher/](publisher/README.md) | Stage 2 MQTT replay client |
| [database/](database/README.md) | MySQL schema and versioned migrations |
| [dashboard/](dashboard/README.md) | Node-RED operator page and HTTPS API proxy |
| [mosquitto/](mosquitto/README.md) | MQTT broker TLS and access-control configuration |
| [infrastructure/](infrastructure/README.md) | Local TLS certificate and credential provisioning |
| [tests/](tests/README.md) | Unit and dataset-backed tests |
| [ml_processor/](ml_processor/README.md) | Stage 1 model evaluation, Stage 2 assignments, and operational flags |
| [planing/](planing/) | Milestone plans retained from earlier project work |

## Dataset

The supplied [dataset-IdC-2627/](dataset-IdC-2627/) contains `stations.json` (83 stations), `stage1_offline.jsonl` (13–19 March 2024; 53,724 records), and `stage2_online.jsonl` (20–22 March 2024; 19,856 records). Source timestamps carry the UTC−04:00 offset. Event field names and validation rules are based on these supplied records.

## First-time local setup

Prerequisites: Docker Desktop with Compose, Python 3.11 or later, and OpenSSL. Run from the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
# Edit .env and set GROUP_NUMBER to your assigned two-digit group.
python infrastructure\setup_local.py
docker compose up -d --build --wait
```

The setup script reads `GROUP_NUMBER` from `.env`, creates local-only credentials and development certificates in `.local/`, and refuses to overwrite an existing `.local/` directory. It uses Docker to generate broker and dashboard password hashes. Do not commit `.local/` or its keys/passwords.

MQTT topics use the configured group, for example `idc/fcXX/status/<station_id>`, `idc/fcXX/trips/started`, and `idc/fcXX/trips/ended`. The Compose MQTT listener is TLS on port 1883. Set `MQTT_BIND` in `.env` to control its host binding; the default permits remote clients, so expose it only on a trusted network and distribute the development CA securely.

The Node-RED page is at **https://localhost:1880/bike-sharing**. The editor and HTTP flows require basic authentication (`admin`); the generated password is in `.local/dashboard/admin.password`. The browser must trust `.local/certs/ca.crt` to avoid a certificate warning.

The station map is available at **https://localhost:1880/bike-sharing/map**. Analytics and map pages refresh sequentially every five seconds while active, pause while the browser tab is hidden, retain the last successful view on failures, and retry transient errors. English and Portuguese (Portugal) labels are available without a page reload. Displayed results use `dd/mm/yyyy hh:mm` and the source UTC−04:00 offset; native date/time filter formatting depends on the browser.

Station profiles are available at **https://localhost:1880/bike-sharing/profiles**. They refresh every 30 seconds and use the selected date range by local calendar day. The dedicated ML service refreshes persisted profiles every `ML_REFRESH_SECONDS` (default 60 seconds); the initial ML model is created after Stage 1 data is available. If the Stage 2 replay is still running, the service updates the affected daily profiles on its next refresh.

After changing processor, ML, or dashboard code, run `docker compose up -d --build --wait processor ml-processor dashboard` to replace outdated images. Port 8765 is not a project service. The dashboard reads committed data from the processor and database, not directly from Mosquitto; Stage 2 MQTT messages appear only when the replay publisher is running or has already published them.

Leaflet JavaScript/CSS assets are installed from the pinned `dashboard/package-lock.json` during the dashboard image build and served locally. Street tiles come from OpenStreetMap over HTTPS with visible attribution. Using the tile service requires internet and reveals the browser IP and viewed map area to that provider; the dashboard sends no application data or credentials to it. If tiles are unavailable, station locations and the accessible station list remain available.

## Load Stage 1 data

The running processor container has the dataset and schema mounted. Run:

```powershell
docker compose exec -T processor python -m processor load-offline `
  --stations /app/dataset-IdC-2627/stations.json `
  --schema /app/database/schema.sql `
  /app/dataset-IdC-2627/stage1_offline.jsonl
```

The loader uses the mounted database password and CA certificate. It stores valid and warning-bearing records, quarantines invalid records with their source location, and records changed-payload sequence conflicts rather than overwriting the first event. Re-running an unchanged file is safe.

## Replay Stage 2

Set `REPLAY_SPEED` in `.env` (for example `600`) and run:

```powershell
docker compose --profile replay run --build --rm publisher
```

The publisher preserves the source inter-message intervals divided by the speed multiplier. Its persistent checkpoint advances in batches of 100 only after QoS 1 broker acknowledgments (and is saved at end of file); after a crash, up to 99 acknowledged events can be replayed. This does not confirm that the processor has finished storing every message. The broker keeps queued QoS 1 messages for the persistent processor session, and ingestion remains idempotent because MQTT can redeliver. Wait for the subscriber to drain its queue and verify database counts before relying on the final aggregates. A completed checkpoint prevents an accidental second full replay. To intentionally reset the checkpoint and replay from the beginning:

```powershell
docker compose --profile replay run --rm --entrypoint python publisher -m publisher --reset
```

Changing the dataset, group, or replay speed invalidates an existing checkpoint and requires an explicit reset.

Stage 2 is stored separately from Stage 1. After applying migration 004 to an existing installation, legacy Stage 2 rows remain in `events` for audit but are ignored by current dashboards and ML profiles. Reset the publisher checkpoint once to repopulate the MQTT stream:

```powershell
docker compose --profile replay run --rm --entrypoint python publisher -m publisher --reset
```

As the publisher replays the dataset, analytics and the station map refresh every five seconds; the profile page refreshes every 30 seconds, and the ML service recomputes the current Stage 2 profiles every 60 seconds by default. Stage 1 events and model training remain unchanged.

## Tests and operations

Install the processor dependencies if needed, then run:

```powershell
python -m pip install -r processor\requirements.txt
python -m pip install -r ml_processor\requirements.txt
python -m unittest discover -s tests -v
npm --prefix dashboard ci
npm --prefix dashboard test
docker compose config --quiet
docker compose ps
```

Useful logs: `docker compose logs processor`, `docker compose logs mosquitto`, and `docker compose logs dashboard`. Use `docker compose down` to stop services without deleting persistent data. Avoid `docker compose down -v` unless you explicitly intend to remove the database and other named volumes.

## Analytics and business assumptions

- The API accepts an explicitly UTC−04:00 `start` and `end` and `bucket=hour|day|week`; ranges are half-open and limited to 31 days.
- The authenticated `/api/stations/latest` endpoint returns reference stations and their latest committed non-rejected status independently of analytics date filters.
- Authenticated `/api/ml/model`, `/api/ml/profiles`, and `/api/ml/flags` endpoints expose the active model metadata, bounded daily assignments/evolution, and explainable flags.
- Weekly buckets start Monday at local midnight.
- Estimated e-bike energy is based on straight-line station distance at 15 Wh/km; classic-bike energy is zero. Missing coordinates leave e-bike energy unknown.
- Fare overage minutes round up; the e-bike surcharge applies to exact trip minutes; the final fare rounds half-up to cents. See [processor/calculations.py](processor/calculations.py) and [processor/README.md](processor/README.md).

## Milestones

- Dataset validation, Compose infrastructure, and Stage 1 persistence are implemented.
- MQTT Stage 2 replay, durable ingestion, calculations, and the historical dashboard are implemented.
- Stage 1 unsupervised profiling, Stage 2 daily assignments/evolution, and explainable underuse/occupancy flags are implemented. Model choice uses unlabeled clustering metrics and does not claim classification accuracy.
- Active-trip UI and automatic rebalancing recommendations remain outside the current implementation.
