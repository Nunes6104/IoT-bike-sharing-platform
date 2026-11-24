# Processor

The Python processor validates and persists offline and MQTT events, and serves the analytics API used by Node-RED.

## Modules

- `validation.py`, `inspect_dataset.py`: inspect the supplied event and station records.
- `event_store.py`: shared idempotent persistence, warning/error handling, and quarantine for offline and MQTT inputs.
- `offline_loader.py`: stream Stage 1 JSONL into MySQL.
- `subscriber.py`: receive MQTT events and acknowledge only after persistence/quarantine completes.
- `calculations.py`, `analytics.py`: fare, energy, duration, trip trends, and observed station utilization.
- `api.py`, `runtime.py`: HTTPS analytics API and combined processor runtime.
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

The dashboard requests `/api/analytics` from the processor over HTTPS with a service bearer token. Analytics require an explicit UTC−04:00 time range; the end is exclusive and periods are limited to 31 days. See the root [README](../README.md) for setup and replay commands.

## Persistence and calculations

Events are keyed by the observed source `seq`. Identical deliveries are no-ops; a changed payload with an existing sequence is audited without replacing the original. Invalid MQTT payloads are quarantined. Source JSON and UTC-converted timestamps are retained. Fare and energy calculations are isolated in `calculations.py`; trips with missing coordinates do not receive invented e-bike energy.

Run focused or full tests from the repository root with `python -m unittest discover -s tests -v`.
