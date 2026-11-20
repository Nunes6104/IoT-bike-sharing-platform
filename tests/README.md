# Tests

This directory contains unit and integration tests for the bike-sharing IoT platform, covering data validation, timezone handling, database persistence, and end-to-end workflows.

## Purpose

Tests verify that:
1. JSON parsing and validation reject malformed and invalid records correctly
2. Timezone conversions from source -04:00 to UTC are accurate and idempotent
3. Warning-bearing records are persisted alongside valid records
4. Errors are quarantined with provenance and original line text
5. Database keying prevents duplicates on reimport
6. Conflicts are detected and logged when key collisions occur
7. The full offline import workflow on supplied dataset produces expected counts

## Contents

### Validation tests (Milestone 1)

- **`test_validation.py`** — 9 unit tests
  - Timezone preservation: source -04:00 offset is kept; naive/wrong-offset timestamps rejected
  - JSON parsing: standard numbers only; NaN/Infinity rejected
  - Trip and status event validation: required fields, type checks, coordinate ranges
  - Station reference validation: duplicate IDs rejected; all required fields present
  - CLI: reports raw bad records, keeps original line text, non-zero exit on errors
  - Warnings do not fail validation; warning records are processable
  - Unknown/outside-reference stations are warnings; invalid types are errors

### Offline loader tests (Milestone 3)

- **`test_offline_loader.py`** — 9 unit tests
  - UTC conversion: source -04:00 wall time converted correctly to UTC
  - Content hashing: canonical JSON hashing enables duplicate detection
  - Dry-run mode: validation without database writes
  - Issue serialization: validation issues JSON-encode for storage
  - Loader stats: counters track records read, processed, warnings, errors, rejects
  - Malformed JSON: categorized as errors, quarantined
  - SQLite support: loader works with both MySQL and SQLite dialects

- **`test_loader_local.py`** — 1 integration test with SQLite
  - Full offline dataset import: all 53,724 events processed
  - Verification: exactly 83 stations, 53,724 events, 126 warnings, 0 errors, 0 rejects
  - Exit code: 0 (success)
  - Database state: events table populated, warning status correct
  - Idempotency: dry-run mode counts events without writing
  - Uses in-memory SQLite for speed and isolation (no Docker/MySQL needed)

### Infrastructure setup tests (Milestone 2)

- **`test_setup_local.py`** — 4 tests for certificate and credential generation
  - Group number validation: requires two-digit value
  - Certificate name validation: rejects invalid DNS names
  - Password file format: uses Unix newlines (not Windows)
  - Overwrite protection: refuses to recreate existing `.local` directory

## Running tests

### All tests

```powershell
python -m unittest discover -s tests -v
```

Expected output: 22 tests, all passing

### Single test file

```powershell
python -m unittest tests.test_validation -v           # Validation only
python -m unittest tests.test_offline_loader -v       # Loader unit tests
python -m unittest tests.test_loader_local -v         # Full integration test (SQLite)
python -m unittest tests.test_setup_local -v          # Infrastructure setup
```

### Single test case

```powershell
python -m unittest tests.test_validation.ValidationTests.test_timezone_is_preserved_and_naive_or_wrong_offset_rejected -v
```

## Test scope and boundaries

### Unit tests (test_validation.py, test_offline_loader.py)

- **In scope:** JSON parsing, validation logic, timezone conversions, hashing, stats tracking, dry-run mode
- **Out of scope:** Real MySQL connections, file I/O performance, network access

### Integration test (test_loader_local.py)

- **In scope:** Full offline dataset (53,724 events) with SQLite backend, verifies exact counts, idempotency
- **Out of scope:** MySQL integration (covered when Docker Compose runs with real database), MQTT connections, online replay

### Setup tests (test_setup_local.py)

- **In scope:** Certificate and credential generation logic, file format, validation
- **Out of scope:** OpenSSL/certificate chain verification (manual), Docker Compose startup

## Test coverage

| Feature | Coverage |
|---------|----------|
| JSON parsing | ✓ Valid and invalid JSON |
| Timestamps | ✓ UTC-04:00 conversion, naive/wrong-offset rejection |
| Event validation | ✓ All event types, required fields, ranges, missing stations |
| Station validation | ✓ Duplicates, required fields, coordinates |
| Hashing | ✓ Canonical JSON, mutation detection |
| Database | ✓ SQLite (dry-run, full import, counts) |
| Error handling | ✓ File errors, parse errors, DB errors |
| Idempotency | ✓ Duplicate key handling (SQLite) |
| CLI | ✓ Exit codes, raw output, error reporting |

## Limitations and future work

- **No real MySQL tests yet:** Integration tests use SQLite; Docker Compose with MySQL will be tested in Milestone 4
- **No TLS certificate validation tests:** Covered by manual testing with real certificates
- **No MQTT tests:** Publisher and subscriber connections deferred to Milestone 4
- **No calculation tests:** Energy, fare, and aggregation logic to be tested in Milestone 4
- **No dashboard tests:** UI verification deferred to Milestone 4

## Running tests in Docker

When the processor container is built and running:

```powershell
docker compose exec processor python -m unittest discover -s tests -v
```

## Test data

All tests use the supplied dataset files:
- `dataset-IdC-2627/stations.json` — 83 stations
- `dataset-IdC-2627/stage1_offline.jsonl` — 53,724 events (Milestone 1 and 3)
- `dataset-IdC-2627/stage2_online.jsonl` — 19,856 events (Milestone 1 only; not used in Milestone 3 yet)

No synthetic or mock data is generated; all tests use real Citi Bike data.

## Related files

- `processor/validation.py` — Validation logic tested by test_validation.py
- `processor/offline_loader.py` — Loader logic tested by test_offline_loader.py
- `infrastructure/setup_local.py` — Setup logic tested by test_setup_local.py
- Root `README.md` — Platform overview and usage
