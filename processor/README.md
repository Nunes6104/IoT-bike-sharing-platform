# Processor

The Python processor validates and persists offline and MQTT events, and serves the analytics API used by Node-RED.

## Modules

- `validation.py`, `inspect_dataset.py`: inspect the supplied event and station records.
- `event_store.py`: idempotent persistence, warning/error handling, and quarantine; offline Stage 1 and MQTT Stage 2 records are routed to separate tables.
- `offline_loader.py`: stream Stage 1 JSONL into MySQL.
- `subscriber.py`: receive MQTT events and acknowledge only after persistence/quarantine completes.
- `calculations.py`, `analytics.py`: fare, energy, duration, trip trends, and observed station utilization.
- `api.py`, `station_snapshot.py`, `runtime.py`: HTTPS analytics and latest station/active-trip snapshot APIs, plus combined processor runtime.
- `station_profiles.py`: bounded queries for active model metadata, station/day cluster evolution, and persisted explainable flags.
- `db.py`, `config.py`: MySQL TLS setup, migrations, and secret-file configuration.
- `__main__.py`: processor CLI.

## Commands

After Compose is running, load Stage 1 with:

```powershell
docker compose exec -T processor python -m processor load-offline `
  --stations /app/dataset-IdC-2627/stations.json `
  --schema /app/database/schema.sql `
  /app/dataset-IdC-2627/stage1_offline.jsonl
```

The Compose runtime starts MQTT ingestion and the HTTPS API automatically. It uses the configured group, MySQL CA, MQTT CA, and mounted secret files. The MQTT broker listener is TLS on port 1883; do not switch to plaintext for convenience.

The dashboard requests `/api/analytics`, `/api/stations/latest`, and the `/api/ml/*` routes over verified HTTPS with a server-side bearer token. Analytics combines immutable Stage 1 records with Stage 2 records received through MQTT; pre-migration Stage 2 rows retained in `events` are not included. Profile date ranges use ISO local dates, an exclusive end, and a 31-day maximum. The snapshot API combines the latest non-rejected Stage 1 or MQTT status, ordered by source timestamp and then sequence, with Stage 2 trip starts whose latest received event by source sequence is still `trip_started`. These are open trips in the replay stream, not guaranteed present-day riders; incomplete source events can remain open. It includes a separate fetch time and latest included event time; missing reports and invalid coordinates remain explicit. No query parameters are supported for the snapshot endpoint. See the root [README](../README.md) for setup and replay commands.

## Persistence and calculations

Offline inputs must have Stage 1 sequence values and are stored in `events`; MQTT inputs must have Stage 2 sequence values and are stored in `online_events`. Both streams are keyed by the observed source `seq`. Identical deliveries are no-ops; a changed payload with an existing sequence is audited without replacing the original. Invalid MQTT payloads and stage-mismatched events are quarantined. Source JSON and UTC-converted timestamps are retained. Fare and energy calculations are isolated in `calculations.py`; trips with missing coordinates do not receive invented e-bike energy.

Run focused or full tests from the repository root with `python -m unittest discover -s tests -v`.
