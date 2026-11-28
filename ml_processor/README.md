# ML Processor

This is the separate station-profiling service. It reads the fixed Stage 1 baseline and MQTT-only Stage 2 records from MySQL over verified TLS, trains an unsupervised model only from Stage 1, and periodically refreshes Stage 1/Stage 2 daily assignments. It does not subscribe to MQTT or alter source events.

## Profile and data rules

- Training windows are 13–19 March 2024; Stage 2 windows are 20–22 March 2024. Dates use the source's explicit UTC−04:00 offset and daily windows are half-open.
- The inspected source files have contiguous unique sequence ranges: Stage 1 `seq=1..53724`, Stage 2 `seq=53725..73580`. The processor uses that observed boundary so Stage 2 rides cannot leak into Stage 1 training. Stage 1 rows remain in `events`; only records received from MQTT enter `online_events`.
- Completed `trip_ended` events contribute once per `ride_id`. Conflicting payloads with the same ride ID are excluded from profile calculations; identical repeated records are counted once. Departures use `started_at`; station arrivals and hourly arrivals use `ended_at`.
- Every reference station receives a station/day row. Missing status observations remain `null` for occupancy/empty/full features, not imputed zero. Occupancy is bikes available divided by reference capacity for observed status updates. No elapsed time empty/full is inferred.
- Trip shares/counts use persisted valid and warning-bearing records. Unknown/out-of-reference start/end stations are excluded only from the corresponding station count and are included in refresh diagnostics. Missing coordinates keep distance and electric energy unknown; coverage features disclose incomplete measurements. Classic-only days have zero electric energy, while days with electric rides and no known distance have unknown energy.
- Candidate numeric features include turnover per dock, member/casual departures and arrivals, hourly departures/arrivals, net arrivals, member/casual/electric shares, duration, known distance/coverage, known electric energy/coverage, reported occupancy/empty/full shares, status observation count, and disabled bikes/docks.

## Model selection and limits

The service evaluates scaled K-Means and diagonal-covariance Gaussian-mixture candidates with 2–8 clusters, rejects candidates with fewer than five profiles in any cluster, and ranks remaining candidates by the sum of ranks for silhouette (higher), Davies–Bouldin (lower), and five-run 80% subsample adjusted-Rand stability (higher). Missing feature values use training medians plus explicit missingness indicators. Model fitting limits BLAS/OpenMP to one worker to prevent container CPU oversubscription. The selected algorithm, parameters, scaler, feature names, metrics, and model identity are persisted in migration 003. A restarted service reuses a compatible active model; a model-format change triggers a Stage 1 retraining while preserving the previous version and assignments.

There are no ground-truth labels; these metrics compare cluster structure and repeatability, not classification accuracy. Only seven Stage 1 days are available, so clusters are short-horizon station profiles, not seasonal or causal findings.

The verified Compose refresh selected three-cluster K-Means for the current model format. On the available Stage 1 profiles it measured silhouette `0.1482`, Davies–Bouldin `2.0454`, subsample stability ARI `0.8720`, and a minimum cluster share of `0.0327`. These are run-specific unsupervised metrics, not target scores or accuracy claims. The prior format-1 model and its assignments remain persisted as history; the format-2 model is active.

Explainable flags are rule-based and never prescribe rebalancing:

- `underused_relative`: station turnover at or below the selected city's daily 10th percentile (default `ML_UNDERUSE_PERCENTILE=0.10`).
- `frequently_empty` / `frequently_full`: at least 50% of valid status reports, with at least four observations (defaults `ML_OCCUPANCY_SHARE_LIMIT=0.50`, `ML_MIN_STATUS_OBSERVATIONS=4`).
- `occupancy_shift`: absolute change in daily mean observed occupancy of at least 0.50 from the prior day, with the same minimum observations (`ML_OCCUPANCY_SHIFT_LIMIT=0.50`).

Thresholds are configurable through `.env`; invalid bounds fail explicitly. Flags include measured values, thresholds, and explanatory bases. An empty profile does not imply an empty or full physical station.

## Run and verify

Compose starts `ml-processor` after the processor schema is available. Database TLS uses the same CA, hostname verification, and secret-file pattern as the event processor. `ML_REFRESH_SECONDS` controls restart-safe refresh polling (default 60; allowed 5–3600). Each refresh retrains only when there is no compatible Stage 1 model, clears and recomputes the active model's Stage 2 profiles from the current MQTT table, and leaves Stage 1 profiles unchanged.

```powershell
python -m pip install -r ml_processor\requirements.txt
python -m unittest tests.test_ml_processor -v
docker compose up -d --build --wait ml-processor
docker compose logs ml-processor
```

The processor exposes authenticated HTTPS `/api/ml/model`, `/api/ml/profiles?start=YYYY-MM-DD&end=YYYY-MM-DD`, and `/api/ml/flags?start=YYYY-MM-DD&end=YYYY-MM-DD` endpoints. The Node-RED dashboard proxies them without exposing the bearer token to browser code.
