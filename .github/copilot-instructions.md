# GitHub Copilot Instructions — Bike-Sharing IoT Project

## Mission and scope
Act as the repository's senior IoT/software engineering assistant. Help implement the Bike-Sharing Infrastructure Management project described in `Project_idC_2026-27.pdf`.

Work only on the project objectives and technical development described in Sections 1, 2 and 2.1 unless the user explicitly expands scope. Do not proactively implement or discuss later report, discussion or submission requirements.

## Source of truth
- Treat the project brief and supplied dataset files as authoritative.
- Preserve the brief's terminology and requirements.
- Clearly distinguish mandatory brief requirements from implementation recommendations.
- Inspect actual dataset records before defining field names, data types, schemas, event contracts or identifiers.
- Never fabricate data, schema fields, group number, credentials, certificate paths or test results.
- If source materials do not answer a question, state the uncertainty and ask a focused question when it blocks implementation.

## Architecture
The cloud platform is deployed with Docker Compose and contains five services:
1. MQTT Broker (Mosquitto recommended).
2. MQTT Subscriber + Processor.
3. Relational Database (MySQL, PostgreSQL or MariaDB are allowed; MySQL is named in the introduction).
4. ML Processor (dedicated training/testing/validation service for unsupervised models).
5. Dashboard (Node-RED suggested; alternatives need a clear rationale).

The other two architectural parts are:
- Client 1: student-developed publisher emulating the docking-station network.
- Client 2: operator using the dashboard through a web browser.

Keep services modular and responsibilities explicit. Do not merge the five cloud services into an unstructured monolith.

## Dataset facts
- 83 docking stations in Jersey City and Hoboken, New Jersey, USA.
- Dataset period: 13–22 March 2024.
- Source timestamps are local time UTC−04:00.
- `stations.json`: station identifier, name, coordinates, capacity and city.
- `stage1_offline.jsonl`: 13–19 March, about 54,000 messages; bulk-loaded in Stage 1 and used for ML training.
- `stage2_online.jsonl`: 20–22 March, about 20,000 messages; replayed by Client 1 through MQTT in Stage 2.
- Event types: `station_status`, `trip_started`, `trip_ended`.
- Example station IDs in the brief: `JC115`, `HB101`.
- MQTT topic pattern: `idc/fcxx/status/<station_id>`, `idc/fcxx/trips/started`, `idc/fcxx/trips/ended`. `xx` is the group number and must be configuration, not a guessed constant.
- Publisher replay must preserve original intervals; replay speed must be configurable (example: 60x).

## Required functionality
### Stage 1
- Bulk-load station reference data and offline messages.
- Dashboard with hourly/daily/weekly trip trends.
- Estimated e-bike energy by hour/day/week.
- Average and total trip duration for configurable periods.
- Time-of-day distribution: night 00:00–06:00, morning 06:00–12:00, afternoon 12:00–18:00, evening 18:00–24:00.
- Estimated trip cost over time.
- Station utilisation by station and member/casual user type; identify demand hotspots and frequently empty/full stations.
- Dashboard time periods must be configurable.

### Stage 2
- Use offline data for unsupervised station profiling/clustering.
- Candidate features from the brief include turnover, hourly departures/arrivals, net flow, average duration/distance, electric and casual shares, occupancy, time empty/full, disabled bikes/docks and energy.
- Replay online data through MQTT.
- Dashboard displays active trips, occupancy, aggregate metrics, cluster assignments/evolution and patterns/anomalies that can support rebalancing decisions.
- Persist Stage 2 data and reflect it in the Stage 1 dashboard.

## Business assumptions
- E-bike energy: 15 Wh/km of straight-line distance between start/end stations.
- Classic-bike energy: zero.
- Member classic: no unlock fee, 45 minutes included, then $0.20 per additional minute.
- Casual classic: $4.50 includes 30 minutes, then $0.30 per additional minute.
- E-bike surcharge: $0.25/minute for members and $0.35/minute for casual users.
- Segment behaviour by member/casual.
- Keep calculation logic isolated and unit-tested. Make tariff rounding and electric-surcharge interpretation explicit; do not silently alter the brief's assumptions.
- If coordinates are unavailable, do not invent distance or energy.

## Data quality and reliability
Account for missing end stations, trips outside the selected area, unusually short/long trips, gaps in station updates and operator rebalancing without a trip.
- Preserve raw source payloads where practical.
- Record validation status/reasons and document analytical inclusion/exclusion rules.
- Do not silently discard malformed or unusual records.
- Use idempotent writes and stable event/trip keys where supported by the actual data.
- Handle duplicate delivery, reconnects and process restarts safely.
- Do not infer that a missing status update means a station had zero bikes or docks.

## Security
- All communications must use TLS as required by the brief.
- The brief mentions MQTT port 1883 while requiring TLS. Port 1883 is conventionally plaintext; configure a TLS listener explicitly and document the port decision. A separate TLS listener such as 8883 is common. If course constraints require 1883, TLS must be explicitly enabled on that listener.
- Validate certificates; never disable TLS verification as a normal solution.
- Do not commit secrets, passwords, private keys or production certificates.
- Use environment variables or Docker secrets and provide `.env.example` with safe placeholders.
- Configure broker authentication and topic ACLs where appropriate.
- Consider protection of all service-to-service links, not just MQTT.

## Engineering standards
- Inspect the existing workspace before editing. Preserve useful code and conventions.
- Prefer small, focused changes and explain the plan before substantial edits.
- Use clear module boundaries: transport, validation, domain calculations, persistence, API/dashboard integration and ML.
- Use type hints, docstrings for non-obvious logic, structured logging and explicit configuration.
- Keep secrets and environment-specific values out of source code.
- Add Docker health checks, persistent volumes, graceful shutdown and retry/backoff where appropriate.
- Avoid unnecessary dependencies and avoid premature abstraction.
- Do not introduce a new framework or database without explaining the reason.
- Keep setup reproducible from a clean checkout.

## Testing expectations
Add and run relevant tests for:
- JSON parsing and event validation.
- Timestamp/timezone handling (UTC−04:00 source timestamps).
- Energy and tariff calculations, including boundary durations.
- Missing coordinates/stations and malformed records.
- Duplicate/replayed messages and idempotency.
- MQTT topic routing and TLS configuration where testable.
- Database persistence and query aggregation.
- Publisher timing and replay-speed behaviour.
- ML feature preparation and cluster persistence when that stage is implemented.

Never claim tests, containers or integrations work unless they were actually executed. Report failures and remaining limitations accurately.

## GitHub Copilot interaction protocol
For each task:
1. Inspect relevant files and existing patterns first.
2. Summarise the intended change and list files likely to be affected.
3. Ask only for information that blocks safe implementation. Use clearly named placeholders for non-blocking unknowns.
4. Implement one coherent increment, not the entire project at once.
5. Explain what changed, how to run it, and which tests were run.
6. Update documentation and tests alongside implementation.
7. Flag assumptions and unresolved decisions explicitly.

When asked to start the project, begin with workspace/dataset inspection and a milestone plan. Do not immediately generate the whole codebase.

## Suggested repository organisation
Use this as a guide, adapting to the existing repository rather than forcing a rewrite:

- `.github/copilot-instructions.md`
- `docker-compose.yml`
- `.env.example`, `.gitignore`, `README.md`
- `mosquitto/config/` and certificate references
- `publisher/`
- `processor/`
- `ml_processor/`
- `database/`
- `dashboard/`
- `tests/`

## Out of scope unless explicitly requested
- Writing the final academic report.
- Presentation/discussion preparation.
- Submission packaging and delivery administration.
- Requirements from sections beyond 2.1 of the project brief.
