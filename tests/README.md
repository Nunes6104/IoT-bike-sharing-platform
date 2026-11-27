# Tests

This folder contains unit and local integration tests for data validation, ingestion, calculations, analytics, security configuration, and replay behavior.

## Coverage

- Parsing, event validation, source timezone handling, and station references.
- Offline loading, duplicate event handling, conflict audit, and rejected-payload quarantine.
- Fare rounding, e-bike energy, missing coordinates, time-range boundaries, and trend aggregation.
- Analytics API authentication and bad-range handling; TLS connection configuration and migration idempotency.
- Latest station snapshot ordering, warning retention, missing reports/coordinates, and API authentication/query validation.
- MQTT topic routing, replay interval scaling, checkpoint resume, and failed publish handling.
- The dataset-backed SQLite loader integration test.

The tests do not replace the Docker integration checks for real MySQL TLS, broker TLS, or Node-RED. Those services must be started separately for end-to-end verification.

## Run

From the repository root:

```powershell
python -m pip install -r processor\requirements.txt
python -m unittest discover -s tests -v
```

Run an individual module with, for example, `python -m unittest tests.test_replay -v`. See the root [README](../README.md) for Compose checks.

The dashboard's pure date parser/formatter checks use Node.js and its pinned Leaflet install:

```powershell
npm --prefix dashboard ci
npm --prefix dashboard test
```
