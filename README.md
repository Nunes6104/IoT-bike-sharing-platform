# Bike-Sharing IoT Platform

Docker Compose project for the supplied Jersey City and Hoboken bike-share dataset. It includes a MySQL database, TLS-enabled Mosquitto broker, Python event processor, online replay publisher, and Node-RED operator dashboard. The ML container is currently a placeholder; clustering has not been implemented.

## Current functionality

- Loads station reference data and Stage 1 JSONL events into MySQL.
- Validates and stores MQTT events with duplicate protection and quarantine for rejected payloads.
- Replays Stage 2 JSONL events through MQTT with configurable timing and an acknowledgment-based checkpoint.
- Serves a date-filtered dashboard for completed trips, duration, estimated fare and e-bike energy, time-of-day totals, and station utilization.
- Uses TLS for MQTT on port **1883**, MySQL connections, and the dashboard-to-processor API. Port 1883 is explicitly configured as TLS, not plaintext.

The dashboard reports completed trips from `trip_ended` events, grouped by source-local trip start time. Its end date is exclusive. Energy coverage is shown explicitly when coordinates are unavailable; missing station updates are not interpreted as zero bikes or docks. Active-trip displays, ML clusters, and anomaly detection are not implemented.

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
| [ml_processor/](ml_processor/README.md) | Reserved for future ML work; current container is a placeholder |
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

## Tests and operations

Install the processor dependencies if needed, then run:

```powershell
python -m pip install -r processor\requirements.txt
python -m unittest discover -s tests -v
docker compose config --quiet
docker compose ps
```

Useful logs: `docker compose logs processor`, `docker compose logs mosquitto`, and `docker compose logs dashboard`. Use `docker compose down` to stop services without deleting persistent data. Avoid `docker compose down -v` unless you explicitly intend to remove the database and other named volumes.

## Analytics and business assumptions

- The API accepts an explicitly UTC−04:00 `start` and `end` and `bucket=hour|day|week`; ranges are half-open and limited to 31 days.
- Weekly buckets start Monday at local midnight.
- Estimated e-bike energy is based on straight-line station distance at 15 Wh/km; classic-bike energy is zero. Missing coordinates leave e-bike energy unknown.
- Fare overage minutes round up; the e-bike surcharge applies to exact trip minutes; the final fare rounds half-up to cents. See [processor/calculations.py](processor/calculations.py) and [processor/README.md](processor/README.md).

## Milestones

- Dataset validation, Compose infrastructure, and Stage 1 persistence are implemented.
- MQTT Stage 2 replay, durable ingestion, calculations, and the historical dashboard are implemented.
- Unsupervised ML profiling, active-trip UI, and anomaly/rebalancing recommendations remain future work.
