# ML Processor

This directory contains the machine learning service for unsupervised station profiling, clustering, and anomaly detection. The ML Processor trains models on historical offline data and applies them to online streams for operational insights.

## Purpose

The ML Processor (Milestone 5, deferred) enables:
1. **Station clustering** — Group similar stations based on operational features (turnover, duration, demand patterns, e-bike/casual shares, occupancy dynamics)
2. **Cluster persistence** — Store cluster assignments in the database and update as new data arrives
3. **Anomaly detection** — Identify stations with unusual behavior (frequently full, frequently empty, high rebalancing)
4. **Demand forecasting** — Predict peak demand periods by station cluster
5. **Rebalancing recommendations** — Suggest optimal bike redistribution based on cluster characteristics

## Architecture

The ML Processor operates in two phases:

### Phase 1: Offline training (run once per week or month)
1. Query historical events from database
2. Engineer features from raw trip and status events
3. Train unsupervised model (K-means or DBSCAN)
4. Persist cluster centroids and cluster assignments to database
5. Log model metadata (n_clusters, inertia, silhouette score, training date)

### Phase 2: Online inference (continuous)
1. Subscribe to MQTT status and trip updates
2. Accumulate per-station features (turnover, occupancy, duration, etc.)
3. Periodically (every 1–24 hours) assign incoming data to nearest cluster
4. Detect anomalies (outlier distances, occupancy extremes)
5. Publish insights to dashboard via REST API or MQTT

## Contents

### Core modules

- **`feature_engineering.py`** — Feature extraction from raw data (Milestone 5)
  - Per-station aggregations over configurable time windows
  - Features: turnover (trips/dock), hourly arrivals/departures, net flow, mean trip duration/distance, e-bike share, casual-user share, occupancy percentiles, time-empty/full, disabled bikes/docks, estimated energy
  - Handles missing data (e.g., stations with zero trips) gracefully
  - Implements both offline and online feature computation

- **`clustering.py`** — Unsupervised clustering model (Milestone 5)
  - K-means clustering (scikit-learn default; configurable n_clusters)
  - Silhouette score and inertia for model evaluation
  - Cluster centroids serialization for online inference
  - Alternative: DBSCAN for density-based clustering (configurable)
  - Idempotent training: same seed produces same clusters

- **`anomaly_detection.py`** — Outlier and anomaly identification (Milestone 5)
  - Mahalanobis distance from cluster centroid (outlier detection)
  - Occupancy extremes (time-empty > 25%, time-full > 75%)
  - Rebalancing frequency anomalies
  - Returns anomaly flags and severity scores for dashboard

- **`ml_processor.py`** — Main service orchestrator (Milestone 5)
  - Offline training CLI: query database, train model, persist clusters
  - Online inference loop: subscribe to MQTT, compute features, assign clusters, detect anomalies
  - Cluster evolution tracking: logs cluster membership changes over time
  - Graceful shutdown and state recovery

- **`__main__.py`** — CLI entry point (Milestone 5)
  - `train` subcommand: offline model training with configurable feature window and n_clusters
  - `infer` subcommand: online cluster assignment and anomaly detection
  - Argument parsing and error handling
  - Exit codes: 0 success, 1 validation error, 2 file/DB error

### Configuration

- **`requirements.txt`** — Python dependencies
  - scikit-learn (clustering, feature scaling, metrics)
  - pandas (DataFrame manipulation)
  - numpy (numerical operations)
  - SQLAlchemy (database access)
  - PyMySQL (MySQL driver)
  - paho-mqtt (MQTT subscriptions)
  - requests (HTTP API calls)

- **`Dockerfile`** — Container image for the ML service
  - Base: Python 3.11 slim
  - Installs dependencies from `requirements.txt`
  - Runs as the ml_processor cloud service

## Usage

### Environment variables

The ML Processor reads configuration from environment or `.env`:

- `MYSQL_HOST` — Database hostname (default: `database`)
- `MYSQL_PORT` — Database port (default: `3306`)
- `MYSQL_USER` — Database username (from setup_local.py)
- `MYSQL_PASSWORD` — Database password
- `MYSQL_DATABASE` — Database name (default: `bike_sharing`)
- `MQTT_HOST` — Mosquitto broker hostname (default: `mosquitto`)
- `MQTT_PORT` — Mosquitto TLS port (default: `8883`)
- `MQTT_USERNAME` — MQTT subscriber username (default: `subscriber`)
- `MQTT_PASSWORD` — MQTT subscriber password
- `MQTT_CA_CERT` — Path to CA certificate (default: `.local/certs/ca.crt`)
- `MQTT_GROUP_NUMBER` — Group number for topic subscription (required)
- `ML_N_CLUSTERS` — Number of clusters (default: `5`; tuned via elbow method)
- `ML_FEATURE_WINDOW_HOURS` — Hours of recent data for online features (default: `24`)
- `ML_ANOMALY_THRESHOLD` — Mahalanobis distance threshold for outliers (default: `3.0`)

### Offline training (run once after Stage 1 data load)

```powershell
# Train model on Stage 1 offline data (53,724 events)
python -m ml_processor train `
  --db-url mysql+pymysql://bike_app:PASSWORD@database/bike_sharing `
  --start-date 2024-03-13 `
  --end-date 2024-03-19 `
  --n-clusters 5 `
  --feature-window-hours 24

# Output: Cluster assignments persisted to database, model metadata logged
# Exit code: 0 (success) or 2 (DB error)
```

Options:
- `--db-url` — SQLAlchemy database URL (required)
- `--start-date` — Training data start date in YYYY-MM-DD format (required)
- `--end-date` — Training data end date inclusive (required)
- `--n-clusters` — Number of clusters to discover (default: 5)
- `--feature-window-hours` — Hours to aggregate for each station (default: 24)
- `--dry-run` — Analyze data without training or writing to database

### Online inference (runs continuously during Stage 2)

```powershell
# Subscribe to MQTT and assign incoming events to trained clusters
python -m ml_processor infer `
  --db-url mysql+pymysql://bike_app:PASSWORD@database/bike_sharing `
  --mqtt-host mosquitto `
  --mqtt-port 8883 `
  --mqtt-ca-cert .local/certs/ca.crt `
  --feature-window-hours 24 `
  --anomaly-threshold 3.0

# Output: Cluster assignments and anomalies logged to stderr and database
# Exit code: 0 (continuous; exits only on signal)
```

### Docker Compose

```powershell
docker compose up ml_processor
```

## Model training details

### Feature engineering

For each station and time window, the following features are computed:

| Feature | Description | Unit | Computation |
|---------|-------------|------|-------------|
| **turnover** | Trips per dock per day | trips/dock/day | total_trips / docks_available |
| **hourly_departures** | Mean departures per hour | trips/hour | trip_started events / hours |
| **hourly_arrivals** | Mean arrivals per hour | trips/hour | trip_ended events / hours |
| **net_flow** | Departures minus arrivals | trips | departures - arrivals |
| **mean_duration** | Average trip length | seconds | sum(duration) / count(trips) |
| **mean_distance** | Average trip distance | km | sum(distance) / count(trips) |
| **ebike_share** | E-bikes as proportion of trips | 0–1 | ebike_trips / total_trips |
| **casual_share** | Casual users as proportion | 0–1 | casual_trips / total_trips |
| **occupancy_p50** | Median occupancy (bikes available / capacity) | 0–1 | 50th percentile |
| **occupancy_p95** | 95th percentile occupancy | 0–1 | 95th percentile |
| **time_empty** | Fraction of updates with 0 bikes | 0–1 | zero_bike_updates / total_updates |
| **time_full** | Fraction of updates at capacity | 0–1 | capacity_updates / total_updates |
| **disabled_bikes** | Average disabled bikes | count | mean(disabled_bikes from status updates) |
| **estimated_energy** | Estimated e-bike energy | Wh | sum(15 Wh/km * distance for ebikes) |

**Handling missing data:**
- Stations with zero trips → features set to 0 or median cluster value
- Missing end-station distance → energy not estimated; recorded as NULL
- Gaps in status updates → occupancy computed from available data

### Model training

```python
# Pseudocode for offline training
features = engineer_features(events, start_date, end_date, window_hours=24)
features_scaled = StandardScaler().fit_transform(features)

# Elbow method for optimal n_clusters
inertias = []
for n in range(2, 10):
    model = KMeans(n_clusters=n, random_state=42, n_init=10)
    model.fit(features_scaled)
    inertias.append(model.inertia_)
# User selects n_clusters based on elbow curve

# Train final model
model = KMeans(n_clusters=5, random_state=42, n_init=10)
cluster_assignments = model.fit_predict(features_scaled)

# Persist to database
persist_cluster_assignments(cluster_assignments, start_date, end_date)
persist_model_metadata(model.inertia_, model.cluster_centers_, training_date=now())
```

## Cluster interpretation

Clusters represent operational station archetypes. Example clusters:

- **Cluster 0 (High-turnover commuter hubs):** High turnover, high hourly departures, high casual share, low occupancy variance
- **Cluster 1 (Tourist attractions):** High trip duration, high e-bike share, high occupancy variance, frequent empty periods
- **Cluster 2 (Residential):** Low turnover, balanced departures/arrivals, member-heavy, stable occupancy
- **Cluster 3 (Underutilized):** Very low turnover, low mean duration, frequent empty periods, low net flow
- **Cluster 4 (Maintenance/rebalancing):** High disabled bikes, frequent full periods, irregular patterns

Cluster centroids and feature importance guide interpretation.

## Anomaly detection

Anomalies are flagged based on:

1. **Mahalanobis distance > threshold** (default 3.0)
   - Station features are statistical outliers within its cluster
   - Example: Station with 10x normal turnover

2. **Occupancy extremes**
   - `time_empty > 25%` → frequently no bikes available
   - `time_full > 75%` → frequently at capacity
   - Combined with cluster membership: unusual for this station type

3. **Rebalancing frequency**
   - Net flow > ±50% of mean departures → manual rebalancing detected
   - Potential indicator of extreme demand imbalance

4. **Feature change detection**
   - Comparison of current features to cluster centroid
   - Sudden changes (turnover +200%) indicate operational anomalies

## Database schema (Milestone 5)

New tables created by training/inference:

```sql
CREATE TABLE clusters (
  cluster_id INT PRIMARY KEY,
  training_date DATETIME NOT NULL,
  n_clusters INT NOT NULL,
  model_type VARCHAR(50),  -- 'kmeans', 'dbscan'
  silhouette_score FLOAT,
  inertia FLOAT,
  feature_window_hours INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cluster_assignments (
  station_id VARCHAR(10) NOT NULL,
  cluster_id INT NOT NULL,
  training_date DATETIME NOT NULL,
  centroid_distance FLOAT,  -- Mahalanobis or Euclidean distance to centroid
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (station_id, training_date),
  FOREIGN KEY (cluster_id) REFERENCES clusters(cluster_id)
);

CREATE TABLE station_features (
  station_id VARCHAR(10) NOT NULL,
  computed_at DATETIME NOT NULL,
  feature_window_hours INT,
  turnover FLOAT,
  hourly_departures FLOAT,
  hourly_arrivals FLOAT,
  net_flow FLOAT,
  mean_duration FLOAT,
  mean_distance FLOAT,
  ebike_share FLOAT,
  casual_share FLOAT,
  occupancy_p50 FLOAT,
  occupancy_p95 FLOAT,
  time_empty FLOAT,
  time_full FLOAT,
  disabled_bikes FLOAT,
  estimated_energy FLOAT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (station_id, computed_at, feature_window_hours)
);

CREATE TABLE anomalies (
  station_id VARCHAR(10) NOT NULL,
  detected_at DATETIME NOT NULL,
  anomaly_type VARCHAR(50),  -- 'outlier', 'occupancy_extreme', 'rebalancing', 'feature_change'
  severity FLOAT,  -- 0–1 or Mahalanobis distance
  description TEXT,
  related_cluster INT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (station_id, detected_at, anomaly_type)
);
```

## Limitations and future work

- **No time-series forecasting** — Model does not predict future demand; uses current snapshot only
- **Static clusters** — Clusters retrained offline; online assignments only classify new data
- **No feedback loop** — Anomaly detection does not adapt based on operator actions
- **Limited interpretability** — Cluster meaning derived from feature inspection, not explicit rules
- **No deep learning** — Uses scikit-learn classical ML; could benefit from neural networks for complex patterns

## Related files

- `processor/__main__.py` — Subscriber that persists events to database
- `database/schema.sql` — Database schema for model metadata and assignments
- `dashboard/` — Visualization of cluster assignments and anomalies
- `mosquitto/README.md` — MQTT topic configuration
- `docker-compose.yml` — Service definition for ml_processor
- Root `README.md` — Platform overview
