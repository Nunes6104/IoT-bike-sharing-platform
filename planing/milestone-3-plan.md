# Milestone 3: Offline data foundation (Stage 1 import and persistence)

## Problem and approach

The five-service Compose infrastructure exists (Mosquitto, MySQL, processor container, ML service stub, and dashboard stub) with TLS enabled. Milestone 2 set up certificates, secrets, and configuration; Milestone 1 validated the dataset with zero errors and 151 warnings across 73,580 events.

Build a small, focused Stage 1 foundation that:
1. **Designs and applies a versioned MySQL schema** that preserves raw payloads, source identity, event sequence, timestamps and validation/rejection reasons.
2. **Implements a one-off offline loader** that reuses existing validation logic, streams the files, persists valid and warning-only records, quarantines malformed/invalid lines, and returns non-zero exit status if any were rejected.
3. **Makes imports repeatable and safe** using the dataset `seq` as event keys and stable source-content identity for rejected lines; unchanged data must not create duplicates; conflicting keys must be reported.
4. **Wires the runtime securely** with minimal MySQL driver support, TLS certificate verification, read-only data/secret mounts, and no hardcoded credentials.
5. **Validates everything works** on the supplied offline dataset: 83 stations and all 53,724 event records, 126 warning-bearing records, zero validation errors, and unchanged counts after reimport.

## Scope boundaries

**In scope:** MySQL schema design, offline loader with validation reuse, idempotent persistence, TLS configuration, unit tests for timestamps/warnings/malformed lines/duplicates, integration tests with isolated Compose project, and documentation.

**Out of scope:** Dashboard queries, analytical aggregations, MQTT replay, online import, ML, online processor service, fare/energy calculations, and reporting rejected records to an operator.

## Datasets and evidence

- `stations.json`: 83 stations, unique IDs, all required fields valid.
- `stage1_offline.jsonl`: 53,724 events (16,560 status, 18,585 started, 18,579 ended), sequence 1–53724, zero validation errors, 126 warning-bearing records.
- Dataset field types confirmed: timestamps with explicit `-04:00` offset, integers for counts/seq, strings for IDs/names, floats for coordinates.
- Missing station end-station IDs (77), outside-reference end-station IDs (49), and missing end coordinates (6) are warnings; records are stored.

## Todos

1. **Design the MySQL schema** (`database/schema.sql`)
   - Create versioned migrations: version tracking table, stations reference, events, and quarantine tables.
   - Preserve raw JSON payloads in TEXT/LONGTEXT columns; never infer or truncate.
   - Store `seq` as the event primary key (since it is unique and continues across both files).
   - Store UTC-converted timestamps and preserve the original source text for every record.
   - For stations: ID as primary key, payload, insertion/update timestamps.
   - For events: seq as primary key, type, UTC timestamp, payload, validation status (valid/warning/rejected), and reason text.
   - For rejected lines: file path, line number, raw text, validation issues (JSON array), insertion timestamp.
   - Use constraints that do NOT enforce referential integrity on stations (allow trips to/from outside areas).
   - Document timezone/UTC storage decision explicitly in schema comments.

2. **Implement the offline loader** (`processor/offline_loader.py`)
   - Command: `python -m processor.offline_loader --stations <path> --db-url <url> <files...>`
   - Reuse `validation.load_station_ids()` and `validate_event()` from Milestone 1.
   - Stream files line-by-line; never read the entire event file into memory.
   - Validate stations first; fail with error if reference data is invalid or unreachable.
   - For each event: parse JSON, validate, categorize as valid/warning/rejected.
   - Write valid and warning-bearing events; write rejected lines to quarantine with provenance.
   - Use dataset `seq` as event key: if key exists, check content hash; if hash matches, skip; if hash differs, record conflict and log error; if key is new, insert.
   - For rejected lines: use (file path, line number) as compound key to prevent re-quarantining the same error.
   - Use a single transaction per file (or bounded transactions if resumable behavior is needed); continue processing even after validation warnings.
   - Return exit code 0 if all records passed validation (zero errors), 1 if any records had validation errors, 2 for unreadable files or database connection failures.
   - Log summary: stations loaded, events processed, warning records, error records, database inserts/updates/conflicts.

3. **Create the processor CLI and database connection** (`processor/db.py`, `processor/__main__.py`)
   - Minimal SQLAlchemy setup: connection pooling, TLS certificate verification.
   - Parse DB connection URL from environment or CLI argument.
   - Load CA certificate from filesystem; validate server certificate over TLS.
   - Reuse existing `validation.py`; keep concerns separated (transport, validation, persistence).
   - Extract database URL from Docker environment or `.env.example` placeholder.

4. **Add processor Dockerfile and dependency manifest** (`processor/Dockerfile`, `processor/requirements.txt`)
   - Base: Python 3.11+ slim image.
   - Install SQLAlchemy, PyMySQL (or mysql-connector-python), and dependencies.
   - Use multi-stage build if needed for size; include health check.
   - Run the loader as `ENTRYPOINT` or via Python `-m` module.
   - Mount dataset and secrets as read-only volumes in Compose.

5. **Write unit and integration tests** (`tests/test_offline_loader.py`, `tests/integration_loader.py`)
   - **Unit tests:** timezone conversion (source UTC−04:00 to UTC storage), warning records, malformed JSON, duplicate keys with same content (should not reinsert), duplicate keys with different content (should log conflict), rejected line quarantine, file read errors.
   - **Integration tests:** 
     - Use a disposable Compose project with an isolated MySQL volume.
     - Set up DB, run migration, import full offline dataset.
     - Verify: 83 stations loaded, 53,724 events processed, 126 warning-bearing records persisted, zero rejected records, zero validation errors.
     - Re-import: same counts, no duplicates created, no conflicts reported.
     - Verify TLS: reject plaintext, reject self-signed or bad certificate, accept valid certificate chain.
     - Interrupt and resume: if implemented, verify bounded transactions allow safe recovery.
   - Report actual counts and exit codes; do not assume success.

6. **Update README** (`README.md`)
   - Add Milestone 3 section: database schema, UTC storage, inclusion/exclusion rules.
   - Add setup instructions: `.env.example` template with DB URL and certificate paths, running `setup_local.py` to generate secrets/certs.
   - Add migration/import commands: `docker-compose exec processor python -m processor.offline_loader --stations dataset-IdC-2627/stations.json <db-url> dataset-IdC-2627/stage1_offline.jsonl`
   - Document exit codes and error reporting.
   - Clarify data-quality choices: warnings are not dropped, missing coordinates/stations are preserved, UTC conversion method, and original payloads remain available.
   - Note remaining limitations: no rebalancing inference, no duplicate-message idempotency across different sources, no online/Stage 2 yet, calculations not implemented.

## Likely files to create/modify

**New:**
- `database/schema.sql` — versioned migrations
- `processor/offline_loader.py` — main loader logic
- `processor/db.py` — connection and TLS setup
- `processor/__main__.py` — CLI entry point
- `processor/requirements.txt` — SQLAlchemy, PyMySQL
- `processor/Dockerfile` — container image
- `tests/test_offline_loader.py` — unit tests
- `tests/integration_loader.py` — integration tests (disposable Compose, isolated volume)
- `.env.example` — update with DB connection placeholders

**Modified:**
- `README.md` — Milestone 3 section and usage
- `docker-compose.yml` — add processor volume mounts for dataset and credentials (read-only), define depends_on, set environment variables

## Notes and boundaries

- **UTC storage:** Explicitly configure MySQL session timezone to UTC; store all timestamps as UTC in `DATETIME` columns; preserve original source text so the `-04:00` offset is recoverable.
- **No inference:** Do not infer missing stations as local rebalancing; do not drop unusual records; preserve all data and store validation findings.
- **Idempotency:** Use `seq` as event key; check content hash on key collision; use (file, line_number) as rejected-line key to prevent re-quarantining the same error.
- **TLS validation:** Verify CA certificate chain; never skip verification in normal operation; plaintext access should fail fast and clearly.
- **No real imports during tests:** Use disposable volumes and isolated Compose projects; do not assume success.
- **File streaming:** Process events line-by-line to handle large files; do not read entire JSONL into memory.
- **Stage 2 offline:** This milestone imports only `stage1_offline.jsonl`. The online file (`stage2_online.jsonl`) remains for Milestone 4 (MQTT replay and online processor).

## Success criteria

1. All 9 existing validation tests pass (unchanged).
2. New unit tests cover timezone, warnings, malformed records, duplicates, conflicts, rejected quarantine, and file errors.
3. Integration test on full offline dataset:
   - Exactly 83 stations loaded, 53,724 events processed, 126 warning-bearing records persisted, zero rejected records, zero validation errors.
   - Exit code 0.
   - After reimport: same counts, no duplicates, no new conflicts.
4. TLS integration test: plaintext access rejected; invalid certificate rejected; valid certificate accepted.
5. README updated with schema, UTC storage, setup commands, exit codes, and data-quality notes.
6. No secrets or hardcoded credentials in source code or logs.
7. Zero exit-code variance from expected behavior: zero errors on supplied dataset.
