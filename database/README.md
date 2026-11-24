# Database

This folder defines the MySQL schema and migrations used by the processor.

## Schema and records

- `schema.sql` creates the base schema: `schema_versions`, `stations`, `events`, `rejected_lines`, `event_conflicts`, and the `event_summary` view.
- `migrations/002_online_ingestion.sql` adds the quarantine table for rejected MQTT messages and a unique key for conflict audit records.
- `events.seq` is the event key. The original source payload is retained; source timestamps are converted to UTC for the `DATETIME` column.
- Warning-bearing events are stored with their validation reasons. Invalid file lines and MQTT payloads are quarantined with source information; changed sequence payloads are audited without replacing the original.

All processor MySQL connections require TLS, CA verification, and hostname identity verification. Compose enables MySQL `require_secure_transport`; the database volume persists across ordinary container restarts.

The processor applies the base schema and numbered unapplied migrations. To load historical data, use the `load-offline` command documented in the root [README](../README.md). Do not delete the Compose database volume unless its data is intentionally disposable.
