# Database

This directory contains the relational database schema and initialization logic for the bike-sharing IoT platform.

## Purpose

The database persists station reference data, validated events, and audit records (validation errors and conflicts) with explicit handling of timezone semantics, raw data preservation, and data-quality tracking. It serves as the system of record for all historical and real-time trip and status information.

## Contents

### Schema

- **`schema.sql`** — Versioned MySQL database migrations
  - **schema_versions** — Tracks applied migrations (version 1 is current)
  - **stations** — 83 Jersey City and Hoboken station references
    - Primary key: `station_id`
    - Payload: Complete raw JSON from `stations.json`
    - Timestamps: `created_at`, `updated_at` (UTC)
  - **events** — Trip and status updates
    - Primary key: `seq` (globally unique 1–73,580)
    - Columns: `type` (station_status/trip_started/trip_ended), `ts_utc` (UTC), `payload` (raw JSON), `validation_status` (valid/warning/rejected), `validation_reason` (JSON array of issues)
    - Indexes on type, ts_utc, validation_status for query performance
  - **rejected_lines** — Quarantine for malformed or invalid records
    - Primary key: (source_path, line_number)
    - Payload: Raw original line, validation issues
    - Prevents re-quarantining the same error
  - **event_conflicts** — Conflict log for key collisions
    - Tracks seq, old/new content hashes, and payloads
    - Detects if re-imported data differs from stored data
  - **event_summary view** — Audit counts by event type and validation status

## Storage conventions

### Timezone handling

- All timestamps stored in `DATETIME` columns without timezone info
- Database session timezone explicitly set to UTC (`+00:00`) on every connection
- Original source timestamps (UTC-04:00) preserved in `payload` JSON for every record
- Conversion from -04:00 source to UTC is performed by the processor (`offline_loader.py`)

Example:
- Source event: `"ts":"2024-03-20T14:30:00-04:00"` (EDT, 2:30 PM local)
- Stored: `ts_utc = 2024-03-20 18:30:00` (UTC, 6:30 PM UTC)
- Original: `payload` contains full JSON with original `-04:00` offset

### Data preservation

- Raw JSON payloads stored in `LONGTEXT` columns for every station and event
- Original line numbers preserved for rejected records (source_path, line_number)
- Original JSONL line text preserved in rejected_lines for audit and recovery
- No data inference: missing stations, coordinates, or end-station IDs are not invented

### Validation status semantics

- **valid** — Zero validation issues; record passed all checks
- **warning** — One or more warnings present (e.g., missing end-station); record is eligible for analysis
- **rejected** — One or more errors; record quarantined to rejected_lines table, not persisted as an event

## Schema application

The schema is versioned and idempotent:

1. On first connection, `schema_versions` table is created
2. The loader checks if version 1 exists; if not, all statements are executed
3. Existing tables are not dropped or truncated; `CREATE TABLE IF NOT EXISTS` ensures safety
4. Can be safely applied to an existing database with data: no data loss

Apply schema:
```powershell
python -m processor.load-offline `
  --schema database\schema.sql `
  ...
```

Or manually:
```powershell
mysql -h database -u root -p bike_sharing < database\schema.sql
```

## Referential integrity

- **No foreign-key constraints on station IDs** — Trips to/from outside-area stations and trips with missing end-station IDs are stored and analyzed, not rejected
- **Seq is not enforced as sequential** — Events are keyed by their dataset seq; gaps or duplicates are logged but do not block insertion
- Station reference data is loaded before events; validation fails if reference is missing or invalid

## Indices and performance

- Indexes on `events.type`, `events.ts_utc`, `events.validation_status`, `created_at` for dashboard and audit queries
- Composite primary key on `rejected_lines (source_path, line_number)` for fast conflict detection

## Related files

- `processor/db.py` — Database connection and schema application logic
- `processor/offline_loader.py` — Populates stations and events tables
- `processor/__main__.py` — CLI that invokes schema application and loader
- Root `README.md` — Overall platform design and usage
