# Tests

This folder contains unit and local integration tests for data validation, ingestion, calculations, analytics, security configuration, and replay behavior.

## Coverage

- Parsing, event validation, source timezone handling, and station references.
- Offline loading, duplicate event handling, conflict audit, and rejected-payload quarantine.
- Stage 1/Stage 2 source routing, immutable offline records, and live-query exclusion of archived MQTT rows.
- Fare rounding, e-bike energy, missing coordinates, time-range boundaries, and trend aggregation.
- Analytics API authentication and bad-range handling; TLS connection configuration and migration idempotency.
- Latest station snapshot ordering, warning retention, missing reports/coordinates, and API authentication/query validation.
- Stage 2 active-trip snapshots, including matched starts/ends, historical Stage 1 starts, and rejected end events.
- MQTT topic routing, replay interval scaling, checkpoint resume, and failed publish handling.
- Station/day feature windows, trip de-duplication, missing energy/occupancy, clustering model persistence/prediction, explainable flags, and authenticated ML API range/evolution behavior.
- The dataset-backed SQLite loader integration test.

The tests do not replace the Docker integration checks for real MySQL TLS, broker TLS, or Node-RED. Those services must be started separately for end-to-end verification.

## Run

From the repository root:

```powershell
python -m pip install -r processor\requirements.txt
python -m pip install -r ml_processor\requirements.txt
python -m unittest discover -s tests -v
```

Run an individual module with, for example, `python -m unittest tests.test_replay -v`. See the root [README](../README.md) for Compose checks.

The dashboard's pure date parser/formatter checks use Node.js and its pinned Leaflet install:

```powershell
npm --prefix dashboard ci
npm --prefix dashboard test
```
