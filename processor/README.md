# Processor

This module contains the data ingestion, validation, and persistence logic for the bike-sharing IoT platform.

## Purpose

The processor receives raw event data from MQTT and batch imports, validates records against a schema, persists valid and warning-bearing events to MySQL, and quarantines errors for audit. It bridges the MQTT broker and the database, ensuring data quality and idempotent imports.

## Contents

### Core modules

- **`validation.py`** — Dataset validation logic (Milestone 1)
  - Parses JSON records and enforces non-standard number restrictions
  - Validates timestamps (ISO 8601 with explicit -04:00 offset)
  - Checks event types, required fields, numeric ranges
  - Categorizes issues as errors (invalid/required) or warnings (unavailable/out-of-area)
  - Reuses `load_station_ids()` to validate station references

- **`inspect_dataset.py`** — Command-line tool for batch validation (Milestone 1)
  - Streams JSONL files and validates every line
  - Reports raw bad records with line numbers and issue details
  - Outputs findings as JSON Lines to stdout, summary to stderr
  - Exit codes: 0 no errors, 1 validation errors, 2 file/parse failures

- **`offline_loader.py`** — Offline Stage 1 JSONL import (Milestone 3)
  - Loads stations from `stations.json` and events from JSONL files
  - Reuses validation logic to categorize records
  - Persists valid and warning-bearing records; quarantines errors
  - Implements idempotent keying by event `seq` to prevent duplicates
  - Converts source -04:00 timestamps to UTC for storage
  - Detects key collisions and logs conflicts
  - Exit codes: 0 success, 1 validation errors, 2 file/DB failures

- **`db.py`** — Database connection and schema setup (Milestone 3)
  - Creates secure MySQL connections with TLS certificate verification
  - Loads and validates CA certificate for server identity
  - Applies versioned schema migrations to initialize or upgrade database
  - Supports SQLAlchemy connection pooling and pool pre-ping for resilience
  - Explicit UTC timezone configuration on each connection

- **`__main__.py`** — CLI entry point (Milestone 3)
  - Parses `load-offline` subcommand with arguments
  - Coordinates station loading, event processing, and schema application
  - Handles errors and returns appropriate exit codes
  - Logs summary statistics to stderr

### Configuration

- **`requirements.txt`** — Python dependencies
  - SQLAlchemy (database ORM)
  - PyMySQL (MySQL driver with TLS support)

- **`Dockerfile`** — Container image for the processor service
  - Base: Python 3.11 slim
  - Installs dependencies from `requirements.txt`
  - Copies application code and schema
  - Runs as the processor cloud service

## Usage

### Validation only (Milestone 1, no database required)

```powershell
# Validate offline dataset, report findings to file
python -m processor.inspect_dataset `
  --stations dataset-IdC-2627\stations.json `
  dataset-IdC-2627\stage1_offline.jsonl `
  dataset-IdC-2627\stage2_online.jsonl > findings.jsonl
```

### Load offline data to MySQL (Milestone 3, database required)

```powershell
# Load Stage 1 offline events with schema application
python -m processor.load-offline `
  --stations dataset-IdC-2627\stations.json `
  --db-url mysql+pymysql://bike_app:PASSWORD@localhost/bike_sharing `
  --ca-cert .local\certs\ca.crt `
  --schema database\schema.sql `
  dataset-IdC-2627\stage1_offline.jsonl
```

Options:
- `--stations` — Path to station reference JSON (required)
- `--db-url` — SQLAlchemy database connection URL (required)
- `--ca-cert` — Path to CA certificate for TLS verification (optional but recommended)
- `--schema` — Path to schema SQL file (optional; if provided, applies migrations)
- `--dry-run` — Validate but do not write to database
- `files` — One or more JSONL event files to load

## Data flow

1. **Input:** JSONL files with raw station status and trip events (UTC-04:00 timestamps)
2. **Validation:** Each record checked against schema (type, fields, ranges, timestamps)
3. **Categorization:** Records classified as valid, warning-bearing, or rejected
4. **Persistence:** Valid and warning records → database; errors → quarantine table
5. **Output:** Summary statistics and exit code indicating success or failure

## Key decisions

- **Stream processing:** Events are processed line-by-line to handle large files without loading into memory
- **Reuse validation:** `inspect_dataset.py` and `offline_loader.py` both use the same `validate_event()` function to ensure consistency
- **Preserve warnings:** Warning-bearing records are stored; they are not dropped
- **Idempotent keys:** Event `seq` is the primary key; re-importing identical data creates no duplicates
- **Timezone handling:** Source -04:00 timestamps converted to UTC for storage; original preserved in payload
- **No inference:** Missing stations or coordinates are not invented; records are stored as-is for audit

## Related files

- `database/schema.sql` — Database schema (stations, events, rejected_lines tables)
- `tests/test_validation.py` — Validation tests (Milestone 1)
- `tests/test_offline_loader.py` — Loader unit tests (Milestone 3)
- `tests/test_loader_local.py` — Integration test with SQLite (Milestone 3)
