# Milestone 5: Station profiling, cluster evolution, and operational flags

## Problem and proposed approach

The current platform persists all 73,580 supplied events and serves historical analytics and a latest-station map, but `ml-processor` still runs a placeholder. Implement a separate ML service that derives auditable station/time-window features from the actual persisted schema, trains and validates unsupervised station profiles using Stage 1, saves versioned models and assignments, and periodically applies the selected model to Stage 2 windows. Extend the existing authenticated HTTPS API and Node-RED dashboard to display cluster membership/evolution and explainable anomaly or underuse flags.

Do not add automatic rebalancing recommendations. Keep the existing processor responsible for ingestion and analytics; the dedicated ML service reads persisted data and writes ML results through verified MySQL TLS. Do not infer bike availability from gaps in station reports or fill missing trip distances with invented values.

## Confirmed decisions

- Operator-facing scope: explainable anomaly/underuse flags only; no suggested rebalancing priorities.
- Model evaluation: K-Means baseline plus one alternative, selected using documented unsupervised validation and operational interpretability. There are no ground-truth cluster labels, so do not report classification accuracy.
- Keep ML as its own Compose service, separate from the event processor.
- Preserve the existing TLS/authenticated API and dashboard integration patterns; use additive schema migrations and preserve persisted event data.

## Source-data facts verified

- Stage 1 contains 53,724 events from 13–19 March; Stage 2 contains 19,856 events from 20–22 March. The combined source sequences range 1–73,580.
- `station_status` includes station ID, source timestamp, bikes/e-bikes/docks available and disabled counts, and installed/renting/returning flags.
- `trip_started` includes ride ID, source timestamp, start station/coordinates, user type, and bike type.
- `trip_ended` includes ride ID, start/end timestamps, duration, start/end station and coordinates, user type, and bike type. Some end-station IDs and coordinates are missing; these must remain missing and their coverage must be represented.
- `stations.json` provides station IDs, names, city, coordinates, and capacity. The configured database currently contains 83 stations and all 73,580 events.
- The supplied files have contiguous sequence ranges: Stage 1 uses `seq=1..53724`; Stage 2 uses `seq=53725..73580`.

## Feature and time-window policy

- Use completed `trip_ended` records once per `ride_id` for completed-ride features; do not count corresponding `trip_started` records as additional rides. Use each trip's source-local `started_at` for trip-window assignment, consistent with current dashboard analytics.
- Create station-by-day profiles from Stage 1 (seven source-local days) and Stage 2 (three source-local days). Assign status reports to their own source-local `ts` day. Keep UTC storage and convert to the source UTC−04:00 timezone for window boundaries.
- Candidate features, only where supported by inspected source fields: starts/ends per station and user type, trips per station capacity, hourly demand shape, net flow, member/casual and classic/electric shares, mean duration, known straight-line distance and its coverage, known energy and its coverage, observed occupancy summaries, empty/full report shares, and disabled bikes/docks.
- Normalize/scale numeric features using parameters fit on training data and reuse them for online assignment. Document feature definitions, units, range boundaries, warning inclusion/exclusion, missing-value handling, and minimum-observation requirements. Do not treat unobserved status intervals as empty/full time.

## Implementation tasks

1. **Inspect current integration points and finalize feature contract.** Reuse the actual event and station payloads, current DB TLS helpers, migration runner, API routes, and dashboard patterns. Specify feature calculation and data-quality policies before coding.
2. **Implement feature preparation and model evaluation.** Add a dedicated `ml_processor` package, Dockerfile, pinned requirements, and CLI/service configuration. Generate reproducible station/day feature rows from persisted Stage 1 data. Fit a scaled K-Means baseline and one alternative; evaluate candidate cluster counts with appropriate unsupervised metrics, cluster-size checks, temporal/bootstrap stability, and interpretable feature summaries. Reject unusable or unsupported models explicitly.
3. **Persist model lifecycle and cluster snapshots.** Add a numbered migration for model metadata/serialized parameters, feature-window snapshots, station assignments, and flags as needed. Persist versioned training metrics, feature definitions, assignment timestamps/window boundaries, and source model identity. Make writes idempotent and preserve prior snapshots for evolution; never overwrite source events.
4. **Apply the selected model to Stage 2 and derive flags.** Implement restart-safe scheduled refresh or an explicit refresh command, with the refresh interval and model selection configured. Assign station/day windows from online data and persist comparisons against prior windows. Produce transparent rule-based underuse/anomaly flags from documented feature values and explicit observation thresholds, with no automated operational recommendations.
5. **Expose outputs and extend the operator dashboard.** Add authenticated, bounded API endpoints for model status, station cluster assignments, window-to-window evolution, and explainable flags. Extend Node-RED with cluster membership/evolution and flag tables/charts, loading/error states, and selected local-time ranges. Preserve accessibility and keep the service bearer token server-side.
6. **Test, integrate, and document.** Add focused feature, missingness, model-selection, stability, idempotency, migration, API, and dashboard tests. Verify Stage 1 training, Stage 2 refresh, service restart behavior, TLS database access, and dashboard display using the supplied data and existing Compose stack. Update root, ML, database, processor/API, dashboard, and tests documentation with commands, model metrics/limitations, data-quality rules, and truthful verification results.

## Likely files

- `ml_processor/`: Python package, `Dockerfile`, `requirements.txt`, feature engineering, model evaluation, persistence, runtime, and README.
- `docker-compose.yml`, `.env.example`: ML image/service, TLS database access, and refresh/flag configuration.
- `database/migrations/`: additive tables for versioned models and profile windows.
- `processor/api.py`, `processor/station_profiles.py`, and API tests: authenticated query endpoints for ML outputs.
- `dashboard/flows.json`, frontend assets/tests, and `dashboard/README.md`: cluster/evolution/flag presentation.
- `tests/`: feature and model tests, persistence/API integration tests, and supplied-data checks.

## Acceptance criteria

- Stage 1 training uses persisted source records and produces a reproducible, versioned model with documented unsupervised metrics and feature scaling.
- Every assignment is traceable to a model version, station, source-local window, and feature snapshot. Repeated refreshes do not create duplicate assignments for the same model/window/station.
- Stage 2 cluster snapshots and change/evolution data become visible through the existing authenticated HTTPS dashboard without modifying or recounting source events.
- Flags explain observed values/rules and observation sufficiency; no missing status is converted into an inferred empty/full duration, and no fabricated distance or energy is included.
- Model/service failures remain visible and do not silently replace the last known-good model or return fabricated assignments.
- MySQL TLS and certificate hostname verification remain enabled; secrets stay outside source control.
- Tests and Compose/dashboard integration are executed and reported with measured results. No claim of model accuracy, operational savings, or causal anomaly detection is made without supporting evidence.

## Implementation decisions and limitations

- Candidates are K-Means and Gaussian mixtures with 2–8 clusters; a candidate requires at least five profiles in each cluster. Selection uses the summed ranks of silhouette, Davies–Bouldin, and five-run 80% subsample adjusted-Rand stability. These are unsupervised structural/repeatability metrics, not classification accuracy.
- Feature values missing from a profile are imputed using Stage 1 medians and accompanied by missingness indicators. Features entirely absent in training are excluded.
- Default flags: city-relative 10th-percentile trips-per-dock/day; empty/full share >=50% with at least four status reports; daily mean occupancy shift >=0.50 with at least four reports in each day. These thresholds are configurable.
- Only seven Stage 1 days are available. Results are short-horizon station profiles, not seasonal patterns or causal findings.
- The Stage 2 service refresh uses the supplied sequence/date boundaries for 20–22 March and persists one station/day row for each reference station, preserving unknown status and distance coverage.
