# Bike-Sharing IoT Platform

## Project Status

**Current stage:** Milestone 3 — Offline data loading and MySQL persistence complete.
**Test status:** 22 tests passing (validation + offline loader).
**Dataset status:** 83 stations and 53,724 offline events loaded into MySQL with zero validation errors.

This project implements a Docker Compose-based IoT platform to analyse Citi Bike station and trip data for 83 docking stations in Jersey City and Hoboken, New Jersey (13–22 March 2024, UTC−04:00 local time).

**Architecture:** Five separate cloud services (Mosquitto MQTT broker with TLS, MySQL database, Python processor, Python ML processor, Node-RED dashboard) plus two client components (a publisher replaying online events, an operator using the web dashboard). All communications secured with TLS.

## Quick Reference: Folder Organization

Each major folder has its own README explaining its purpose and usage:

| Folder | Purpose | Key Files |
|--------|---------|-----------|
| [**processor/**](processor/README.md) | MQTT subscriber, data validation, offline/online loading | `validation.py`, `offline_loader.py`, `db.py`, `__main__.py` |
| [**database/**](database/README.md) | Relational database schema and migrations | `schema.sql` (stations, events, rejected_lines tables) |
| [**publisher/**](publisher/README.md) | MQTT publisher client replaying online events | `publisher.py` (Milestone 4) |
| [**mosquitto/**](mosquitto/README.md) | MQTT broker configuration and TLS setup | `mosquitto.conf`, credential and certificate generation |
| [**dashboard/**](dashboard/README.md) | Node-RED operational dashboard for visualization | `flows.json`, real-time and historical analytics (Milestone 4) |
| [**ml_processor/**](ml_processor/README.md) | Unsupervised clustering and anomaly detection | `feature_engineering.py`, `clustering.py`, `anomaly_detection.py` (Milestone 5) |
| [**infrastructure/**](infrastructure/README.md) | Setup automation: certificates, credentials, initialization | `setup_local.py` (Milestone 2) |
| [**tests/**](tests/README.md) | Unit and integration tests for all components | `test_validation.py`, `test_offline_loader.py`, `test_loader_local.py` |

## Milestones

1. **Milestone 1 — Dataset validation** (complete): JSON parsing, timezone handling, event and station validation without data loading. Rejects invalid types and malformed records; preserves warnings. No third-party dependencies.

2. **Milestone 2 — Infrastructure** (complete): Docker Compose with five services (Mosquitto, MySQL, processor placeholder, ML placeholder, Node-RED stub), TLS certificates, random credentials in `.local/` directory, health checks.

3. **Milestone 3 — Offline import** (complete): MySQL schema with versioned migrations, offline JSONL loader with validation reuse, idempotent keying by event sequence, UTC timestamp storage with source payloads preserved, error quarantine with provenance. Verified: 83 stations, 53,724 events, 126 warning-bearing records, zero rejected records, exit code 0.

4. **Milestone 4 — Online stream and aggregation** (pending): TLS-secured MQTT replay of online dataset, event stream processing, analytical aggregations (hourly/daily/weekly trips, energy, fare, duration, utilization), Stage 1 dashboard.

5. **Milestone 5 — ML and advanced analytics** (pending): Unsupervised station clustering from offline features, online cluster evolution, anomaly detection, Stage 2 live dashboard.

## Dataset

The supplied `dataset-IdC-2627` directory contains `stations.json`,
`stage1_offline.jsonl` (13-19 March 2024) and `stage2_online.jsonl` (20-22 March).
See [dataset information](dataset-IdC-2627/info.txt). Source timestamps use local
time with an explicit UTC-04:00 offset. Validation keeps that offset and rejects
naive timestamps or other offsets; a database storage convention will be decided
and documented when persistence is implemented.

## Run validation

Prerequisite: Python 3.10 or later. No third-party packages are needed for this
milestone. From the project root in PowerShell:

```powershell
python -m processor.inspect_dataset --stations dataset-IdC-2627\stations.json dataset-IdC-2627\stage1_offline.jsonl dataset-IdC-2627\stage2_online.jsonl > findings.jsonl
```

Findings are written as JSON Lines to standard output; each contains its source
file, line number, issues and the original line. A summary is printed to standard
error. Exit status is 0 for no errors (including warnings), 1 if any records have
validation errors, and 2 for an unreadable or invalid input file. The command
does not modify the dataset or load it into a database.

Validation checks JSON objects, event type, sequence, timestamps, trip and
station identifiers, supported user and bike types, coordinates and relevant
numeric fields. Missing or outside-reference trip station IDs, unavailable trip
coordinates and electric-bike counts exceeding available bikes are warnings;
invalid types and malformed or missing required fields are errors. Unknown JSON
fields are left untouched. Warnings are not evidence of a zero value. This
inspection is not a full data-quality audit: trip-duration consistency, update
gaps, rebalancing, duplicate delivery and analytical inclusion rules remain to
be addressed in later milestones. No records are imported or excluded here.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Milestone 3: Offline data loading and MySQL persistence

**Goal:** Import the Stage 1 offline dataset (stations and 53,724 events) into
MySQL with idempotent keying, UTC storage, and validation-driven quarantine for
errors.

### Database schema

The schema (`database/schema.sql`) is versioned and includes:

- **stations**: 83 reference stations, one row per unique ID, raw JSON payload preserved
- **events**: Trip and status updates with sequence (seq) as primary key, UTC timestamps,
  raw JSON payload, validation status (valid/warning/rejected), and validation reasons
- **rejected_lines**: Quarantine for malformed JSON or hard validation errors;
  keyed by (source_path, line_number)
- **event_conflicts**: Log for duplicate key collisions where content differs
- **event_summary view**: For auditing counts by type and validation status

**Storage convention:** All timestamps in the database are stored as UTC in
`DATETIME` columns. The original source text with the `-04:00` offset is
preserved in the `payload` column for every record. The session timezone is
explicitly set to UTC (`:00:00`) to avoid implicit conversions.

**Inclusion rules:**

- Valid events (zero validation issues) are stored as `valid`.
- Warning-bearing events (e.g., missing end station or outside-area end station)
  are stored as `warning`; they are **not** excluded or dropped.
- Malformed JSON or hard validation errors (invalid types, missing required fields)
  are quarantined with provenance and original text; processing continues.
- Event records use the dataset `seq` field as the primary key, ensuring
  idempotent imports: re-importing identical data creates no duplicates.
- If a key collision occurs (same seq, different payload), the conflict is logged
  to `event_conflicts` and not silently overwritten.

### Load offline dataset

Prerequisite: `docker compose up -d --wait` has started the MySQL database and
it is accessible at the connection URL.

```powershell
# From the project root:
python -m processor.load-offline `
  --stations dataset-IdC-2627\stations.json `
  --db-url mysql+pymysql://bike_app:$PASSWORD@database/bike_sharing `
  --ca-cert .local\certs\ca.crt `
  --schema database\schema.sql `
  dataset-IdC-2627\stage1_offline.jsonl
```

The command:
- Applies the schema (creates or updates tables).
- Loads and validates the station reference (`stations.json`).
- Streams the event JSONL file line-by-line.
- Validates each event using the existing validation logic from Milestone 1.
- Persists valid and warning-bearing records; quarantines malformed/invalid lines.
- Returns exit code 0 if all events validated successfully (zero errors), 1 if
  any validation errors occurred, and 2 for file/database failures.
- Prints a JSON summary to stderr with counts and results.

**Expected result on the supplied offline dataset:**
- 83 stations loaded
- 53,724 events processed
- 126 warning-bearing records persisted
- 0 validation errors
- 0 rejected records
- Exit code: 0

Re-importing the same file produces unchanged counts and no duplicates.

### Within Docker Compose

To run the loader inside the processor container (after `docker compose up -d --wait`):

```powershell
docker compose exec processor python -m processor.load-offline `
  --stations /app/dataset-IdC-2627/stations.json `
  --db-url mysql+pymysql://bike_app:PLACEHOLDER@database/bike_sharing `
  --ca-cert /run/bike-certs/ca.crt `
  --schema /app/database/schema.sql `
  /app/dataset-IdC-2627/stage1_offline.jsonl
```

(Replace `PLACEHOLDER` with the actual password from `.local/mysql/db-user.password`.)

### Data quality and validation

- **Errors:** Invalid event types, malformed JSON, missing required fields,
  out-of-range numeric values, invalid timestamps.
- **Warnings:** Missing trip end-station ID, trip end-station outside reference
  area, missing end coordinates, electric-bike count exceeding available bikes.
- **Not inferred:** Missing station end-stations are **not** assumed to be local
  rebalancing; trips with missing end coordinates are **not** assigned zero
  distance.
- **Preserved:** Original source payloads and line numbers remain available for
  audit and recovery.

### Limitations

- Only Stage 1 (offline) data is loaded. Stage 2 (online) import and MQTT replay
  are deferred to Milestone 4.
- Calculations (energy, fare, clustering) are not implemented.
- No dashboard or analytical queries yet.
- Duplicate-message idempotency applies only to this supplied dataset stream
  (`seq` as key); other sources would require a different keying strategy.

Compose defines five separate services: Eclipse Mosquitto, MySQL, a Python
processor placeholder, a Python ML processor placeholder, and Node-RED.
The two placeholders only keep their containers running and explicitly log that
they are unimplemented; they do not subscribe, train models, or communicate
with the other services. Node-RED is an authenticated editor with no dashboard
flows yet. No dataset is loaded and no database schema for events exists.
Client 1 (the publisher) is not implemented.

### Install prerequisites on Windows

You need Python 3.10+, Docker Desktop with Docker Compose, and OpenSSL.
The commands below use [WinGet](https://learn.microsoft.com/en-us/windows/package-manager/winget/);
if it is unavailable, use the linked installers instead. Installation may
require administrator approval.

1. **Install Python.** Python 3.13 is a tested choice; another installed
   version of Python 3.10 or later can also be used. See the
   [Python downloads](https://www.python.org/downloads/windows/) page.

   ```powershell
   winget install --id Python.Python.3.13 --exact --source winget
   ```

2. **Install Git for Windows.** Its standard installation includes OpenSSL,
   which the local setup script can find. See the
   [Git for Windows installation page](https://git-scm.com/install/windows).

   ```powershell
   winget install --id Git.Git --exact --source winget
   ```

3. **Install WSL 2 if needed.** Docker Desktop can use the WSL 2 backend;
   check the [Docker system requirements](https://docs.docker.com/desktop/setup/install/windows-install/)
   and enable hardware virtualization if required. If WSL is not already
   installed, run the following in PowerShell **as administrator**, then
   restart Windows. This also installs Ubuntu by default; see the
   [Microsoft WSL instructions](https://learn.microsoft.com/en-us/windows/wsl/install)
   for alternatives.

   ```powershell
   wsl --install
   ```

4. **Install Docker Desktop.** Docker Compose is included; no separate Compose
   installation is necessary. See the
   [Docker Desktop Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).

   ```powershell
   winget install --id Docker.DockerDesktop --exact --source winget
   ```

   Start Docker Desktop from the Start menu, accept its terms, and wait for the
   engine to start. Use Linux containers with the WSL 2 backend.

Close and reopen PowerShell after installation, then verify the tools:

```powershell
python --version
git --version
docker --version
docker compose version
docker info
wsl --version
```

`docker info` should show information about the server, not just the client.
Verify OpenSSL using either the version on `PATH` or the standard Git for
Windows installation path:

```powershell
if (Get-Command openssl -ErrorAction SilentlyContinue) {
    openssl version
} elseif (Test-Path "$env:ProgramFiles\Git\mingw64\bin\openssl.exe") {
    & "$env:ProgramFiles\Git\mingw64\bin\openssl.exe" version
} else {
    Write-Error "OpenSSL was not found. Install it or add it to PATH."
}
```

If Git or OpenSSL was installed elsewhere, add the directory containing
`openssl.exe` to `PATH` and reopen PowerShell. If `python` is not recognized,
check the [Python on Windows troubleshooting guide](https://docs.python.org/3/using/windows.html).

Mosquitto, MySQL, Node-RED, and the Python service runtimes run in containers:
they do **not** need separate host installations. Docker downloads their images
when the stack starts, so internet access is required on the first run.

### Configure and start the project

From the project root in PowerShell:

1. Copy the configuration and edit it to set your actual **two-digit** group
   number. Do not use the example placeholder.

   ```powershell
   Copy-Item .env.example .env
   # Edit .env and set GROUP_NUMBER to your group number.
   ```

2. Generate development certificates and randomly generated credentials:

   ```powershell
   python infrastructure\setup_local.py
   ```

   For access using another host name or IP address, add it to the certificates
   at creation time, for example `--hostname your-host.example`; the option can
   be repeated. The default certificates cover `localhost`, `127.0.0.1`, and
   the applicable Compose service name. The script refuses to overwrite an
   existing `.local` directory. If setup fails, inspect the error and the
   partially created directory before removing or replacing anything.

3. Start and inspect the services:

   ```powershell
   docker compose up -d --wait
   docker compose ps
   docker compose logs --tail 50
   ```

   The broker, database, and Node-RED have health checks. The two placeholder
   services have no application readiness check; a running container does not
   mean the corresponding application has been implemented. Stop the stack with
   `docker compose down`; named volumes are retained.

### Security and access

- Mosquitto listens with TLS on **1883**, as required by the brief. Port 1883
  alone does not imply TLS. MQTT is bound to all host interfaces by default;
  set `MQTT_BIND=127.0.0.1` in `.env` to limit it to the local machine. The
  `publisher` account can publish to the configured group topics, the
  `processor` account can subscribe to them, and a separate account is used
  only for the broker health check. Passwords are in `.local\mosquitto`.
- MySQL is not published to the host. It requires secure transport for network
  connections and uses the `bike_app` account for future application access.
  Clients must trust `.local\certs\ca.crt` and verify the `database` hostname.
  The local Unix socket is not a network connection and is allowed by MySQL.
- Node-RED is available at `https://localhost:1880` and binds to localhost by
  default. Log in as `admin` using the password in
  `.local\dashboard\admin.password`. Browser access requires trusting the
  development CA in `.local\certs\ca.crt`; do not bypass certificate checks.
  `DASHBOARD_BIND` can be changed for remote access, together with a matching
  certificate hostname and appropriate network restrictions.
- The generated CA is **only for local development**. Protect its private key,
  all generated passwords, `.env`, and `.local` from other users. On Windows,
  check and restrict the inherited ACL on the project and `.local` directory;
  POSIX file modes are not a substitute for Windows access control. Neither
  secrets nor private keys belong in version control. Production deployments
  need appropriately trusted certificates, protected secrets, and access
  controls. Certificates expire after 365 days.
- The group number is embedded in the generated MQTT ACL. Changing it requires
  updating that ACL and recreating the broker with
  `docker compose up -d --force-recreate mosquitto`. Keep `.local` and the
  named volumes backed up securely: MySQL initializes passwords only for a new
  data volume, so regenerating files alone does not rotate existing DB
  credentials.
- Future links between application services must use TLS with certificate and
  hostname verification. The current placeholders do not establish such links.

Energy and fare calculations are not implemented. The proposed interpretation
is that the electric surcharge applies to all trip minutes; fare rounding is
still undecided. Missing coordinates must not be replaced with invented distance.

## Implementation notes and decisions

### Project structure

```
├── database/
│   └── schema.sql                 # Versioned MySQL migrations
├── processor/
│   ├── __init__.py
│   ├── __main__.py                # CLI entry point
│   ├── validation.py              # Reused from Milestone 1
│   ├── inspect_dataset.py         # Reused from Milestone 1
│   ├── offline_loader.py          # Offline JSONL import
│   ├── db.py                      # TLS connection and schema setup
│   ├── Dockerfile
│   └── requirements.txt            # SQLAlchemy, PyMySQL
├── tests/
│   ├── test_validation.py         # 9 tests (Milestone 1)
│   ├── test_offline_loader.py     # 9 tests (timezone, hashing, dry-run)
│   └── test_loader_local.py       # Integration test with SQLite
├── mosquitto/, dashboard/, infrastructure/  # Milestone 2 (unchanged)
├── docker-compose.yml
├── .env.example
├── .github/copilot-instructions.md
└── README.md (this file)
```

### Key design choices

1. **Idempotent imports:** Event `seq` is the natural primary key (unique, monotonic, 1–73,580 across both stages). Re-importing identical data creates no duplicates; different content on key collision is logged to `event_conflicts`.

2. **UTC storage with source preservation:** All timestamps stored as UTC in `DATETIME` columns. Original JSON payload with the `-04:00` offset is preserved in `payload` column so the original source time is always recoverable. Database session timezone is explicitly `+00:00`.

3. **Warnings are not dropped:** Records with validation warnings (e.g., missing end-station ID, out-of-area end-station) are stored as `validation_status = 'warning'`. They are eligible for analysis; warnings are not evidence of a zero value.

4. **Quarantine with provenance:** Malformed JSON or hard validation errors are stored in `rejected_lines` with file path, line number, raw text, and issue details. Processing continues after rejection.

5. **No inference:** Missing station end-stations are **not** assumed to be local rebalancing. Missing coordinates are **not** assigned zero distance. All data is preserved for audit.

6. **Reuse of Milestone 1 validation:** The `OfflineLoader` calls `load_station_ids()` and `validate_event()` from `processor/validation.py`, ensuring consistent validation rules and avoiding duplication.

7. **Stream-based processing:** Events are processed line-by-line to handle large JSONL files without loading the entire file into memory.

8. **Multi-database support:** `OfflineLoader` detects the SQLAlchemy dialect and uses MySQL `ON DUPLICATE KEY UPDATE` or SQLite `INSERT OR REPLACE` as appropriate, enabling testing with SQLite before deploying to MySQL.

### Validation and data quality

**Errors (rejected records):**
- Malformed JSON
- Unknown event type
- Missing required fields (e.g., `seq`, `type`, `ts`)
- Invalid types (e.g., `seq` not an integer, coordinates not floats)
- Out-of-range values (e.g., latitude outside −90…90, duration < 0)
- Invalid timestamps (not ISO 8601 with −04:00 offset)

**Warnings (persisted records):**
- Missing trip start-station ID or name
- Missing trip end-station ID or name (77 records in offline dataset)
- End-station outside reference area (49 records)
- Missing end coordinates (6 records)
- Electric-bike count exceeds available bikes

**Audit results on supplied offline dataset:**
- 73,580 total records (stage1 + stage2 combined)
- 53,724 stage 1 offline events
- 83 stations
- 0 validation errors
- 151 warnings across both stages (Milestone 1 output)
- 126 warnings in stage 1 (Milestone 3 input)
- 53,724 events persisted as valid + warning
- 0 rejected records
- Exit code 0

### Limitations and future work

- **No calculations:** Energy consumption (Wh/km), trip cost, and other derived metrics are not yet implemented.
- **No analytics:** Hourly/daily/weekly aggregations, utilization patterns, and time-of-day distributions are deferred to Milestone 4.
- **Online only:** Stage 2 (20–22 March online dataset) import and MQTT replay are not yet implemented; Milestone 4 will add this.
- **No clustering:** Unsupervised station profiling via ML is deferred to Milestone 5.
- **No dashboard:** SQL queries and UI visualizations are not yet implemented.
- **Duplicate idempotency:** The keying strategy (by `seq`) is specific to this supplied dataset stream. Future sources would require different identifiers or a reconciliation strategy.

## Command reference

**Run all tests:**
```powershell
python -m unittest discover -s tests -v
```

**Validate dataset (Milestone 1):**
```powershell
python -m processor.inspect_dataset `
  --stations dataset-IdC-2627\stations.json `
  dataset-IdC-2627\stage1_offline.jsonl `
  dataset-IdC-2627\stage2_online.jsonl > findings.jsonl
```

**Load offline data into local SQLite (testing):**
```powershell
# Schema created automatically for testing; uses SQLite INSERT OR REPLACE
python tests/test_loader_local.py
```

**Load offline data into Docker Compose MySQL (requires running MySQL):**
```powershell
# After: docker compose up -d --wait
$password = Get-Content .local\mysql\db-user.password
python -m processor.load-offline `
  --stations dataset-IdC-2627\stations.json `
  --db-url mysql+pymysql://bike_app:$password@127.0.0.1:3306/bike_sharing `
  --ca-cert .local\certs\ca.crt `
  --schema database\schema.sql `
  dataset-IdC-2627\stage1_offline.jsonl
```

**Generate deployment certificates and credentials:**
```powershell
python infrastructure\setup_local.py
```

**Start or stop the platform:**
```powershell
docker compose up -d --wait      # Start
docker compose ps                 # Check status
docker compose logs --tail 50     # View logs
docker compose down               # Stop (volumes retained)
```

