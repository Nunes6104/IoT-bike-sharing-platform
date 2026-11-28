# Database

This folder defines the MySQL schema and migrations used by the processor.

## Schema and records

- `schema.sql` creates the base schema: `schema_versions`, `stations`, `events`, `rejected_lines`, `event_conflicts`, and the `event_summary` view.
- `migrations/002_online_ingestion.sql` adds the quarantine table for rejected MQTT messages and a unique key for conflict audit records.
- `migrations/003_station_profiles.sql` adds versioned ML model metadata and idempotent station/day profile assignments, including serialized features and flags.
- `migrations/004_stage2_mqtt_events.sql` adds the separate `online_events` table for Stage 2 MQTT data and updates the event summary view.
- `events` contains the immutable Stage 1 baseline; historical Stage 2 rows written before migration 004 remain there for audit but are excluded from live views. New Stage 2 data is accepted only from MQTT into `online_events`.
- Event sequence is the key within each stream. The original source payload is retained; source timestamps are converted to UTC for the `DATETIME` column.
- Warning-bearing events are stored with their validation reasons. Invalid file lines and MQTT payloads are quarantined with source information; changed sequence payloads are audited without replacing the original.

All processor MySQL connections require TLS, CA verification, and hostname identity verification. Compose enables MySQL `require_secure_transport`; the database volume persists across ordinary container restarts.

The ML service stores model parameters, feature transforms, evaluation metrics, daily cluster assignments, and explainable flags in the version-3 tables. Profile rows are keyed by model, station, and local window start; online Stage 2 rows are replaced from the current MQTT stream on each refresh, while Stage 1 model training and profiles remain fixed. Source event tables are not modified by ML work.

The processor applies the base schema and numbered unapplied migrations. To load historical data, use the `load-offline` command documented in the root [README](../README.md). Do not delete the Compose database volume unless its data is intentionally disposable.
