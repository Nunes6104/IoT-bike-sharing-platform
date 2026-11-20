# Dashboard

This directory contains the operational dashboard for the bike-sharing IoT platform, implemented with Node-RED. The dashboard provides real-time and historical visualization of station status, trip trends, energy consumption, and cost analysis.

## Purpose

The dashboard (Client 2 in the architecture) is the primary operator interface for monitoring and analyzing the bike-sharing infrastructure. It displays:

- **Stage 1 (Milestone 4):** Hourly/daily/weekly trip trends, energy consumption, trip cost, station utilization, time-of-day distribution
- **Stage 2 (Milestone 5):** Live occupancy, active trips, cluster assignments, operational anomalies, and rebalancing recommendations

## Architecture

The dashboard is built as a Node-RED application that:
1. Queries the database (MySQL) for historical and aggregated data
2. Subscribes to MQTT topics for real-time station updates
3. Performs client-side aggregations and calculations
4. Renders interactive visualizations via Node-RED Dashboard UI
5. Provides time-range selection for configurable analysis periods

## Contents

### Application structure

- **`flows.json`** — Node-RED flows (Milestone 4)
  - Query nodes for database access
  - MQTT subscription nodes for real-time updates
  - Aggregation functions (hourly, daily, weekly rollups)
  - Calculation nodes for energy and cost
  - Dashboard UI nodes (charts, gauges, text panels)
  - Time-range filter and date picker

- **`settings.js`** — Node-RED runtime configuration (optional, Milestone 4)
  - Database connection pooling
  - MQTT broker configuration
  - Dashboard layout and theme settings
  - API rate limits and caching

### Configuration

- **`requirements.txt`** — Node.js package dependencies
  - node-red (core runtime)
  - node-red-dashboard (UI widgets)
  - node-red-node-mysql (database connector)
  - node-red-contrib-mqtt-broker (MQTT integration)
  - Other visualization and calculation nodes

- **`Dockerfile`** — Container image for the dashboard service
  - Base: Node 18 slim
  - Installs Node-RED and dependencies
  - Mounts flows and configuration
  - Runs dashboard on port 1880

## Usage

### Local development

```powershell
# Install Node-RED globally (optional)
npm install -g node-red

# Install dashboard dependencies
npm install

# Start Node-RED runtime
node-red flows.json --settings settings.js

# Open browser to http://localhost:1880
# Dashboard UI available at http://localhost:1880/ui
```

### Docker Compose

```powershell
docker compose up dashboard

# Open browser to http://localhost:1880/ui
```

### Environment variables

The dashboard reads configuration from environment or `.env`:

- `MYSQL_HOST` — Database hostname (default: `database`)
- `MYSQL_PORT` — Database port (default: `3306`)
- `MYSQL_USER` — Database username (from setup_local.py)
- `MYSQL_PASSWORD` — Database password (from setup_local.py)
- `MYSQL_DATABASE` — Database name (default: `bike_sharing`)
- `MQTT_HOST` — Mosquitto broker hostname (default: `mosquitto`)
- `MQTT_PORT` — Mosquitto TLS port (default: `8883`)
- `MQTT_USERNAME` — MQTT subscriber username (default: `subscriber`)
- `MQTT_PASSWORD` — MQTT subscriber password
- `MQTT_CA_CERT` — Path to CA certificate (default: `.local/certs/ca.crt`)
- `MQTT_GROUP_NUMBER` — Group number for topic subscription (required)
- `DASHBOARD_PORT` — Node-RED dashboard port (default: `1880`)

## Dashboard features

### Stage 1 dashboards (Milestone 4)

#### Trip trends
- **Hourly trip count** — Bar chart of trips per hour over selected date range
- **Daily trip count** — Line chart of trips per day
- **Weekly trip count** — Aggregated weekly totals
- **User type breakdown** — Stacked chart: member vs. casual trips
- **Bike type breakdown** — Classic vs. e-bike trip proportions

#### Energy consumption
- **Estimated e-bike energy (Wh)** — Hourly/daily/weekly totals
- **Energy by user type** — Member vs. casual usage patterns
- **Top energy consumers** — Stations with highest energy usage
- **Energy trend** — Month-over-month or week-over-week comparison

#### Cost analysis
- **Estimated trip cost** — Hourly/daily/weekly revenue
- **Cost by user type** — Member vs. casual fare distribution
- **Average trip cost** — Mean fare per trip
- **Cost trend** — Historical cost variation

#### Trip duration
- **Average trip duration** — Mean duration by selected period
- **Total trip time** — Sum of all trip durations
- **Duration by user type** — Member vs. casual duration patterns
- **Duration distribution** — Histogram of trip lengths

#### Time-of-day analysis
- **Night (00:00–06:00)** — Trips during night hours
- **Morning (06:00–12:00)** — Trips during morning hours
- **Afternoon (12:00–18:00)** — Trips during afternoon hours
- **Evening (18:00–24:00)** — Trips during evening hours
- **Stacked bar chart** — Time-of-day distribution over multiple days

#### Station utilization
- **Station utilization by station** — Table with station name, total trips, member trips, casual trips
- **High-demand stations** — Top 10 stations by trip count
- **Underutilized stations** — Stations with lowest trip volume
- **Member vs. casual by station** — Stacked chart for each station

### Time-range controls (all dashboards)

- **Date range picker** — Select start and end dates
- **Quick presets** — Today, This week, This month, Last 7 days, Last 30 days
- **Hour filter** — Optionally restrict to specific hours (e.g., peak morning)
- **Apply button** — Refresh all visualizations with selected range

### Stage 2 dashboards (Milestone 5, deferred)

#### Live operations
- **Active trips** — Real-time count and map of ongoing trips
- **Station occupancy** — Live bikes/docks available at each station
- **Occupancy gauge** — Percent full/empty per station
- **Occupancy trend** — Historical occupancy pattern for selected station

#### Cluster analysis
- **Station cluster assignments** — Table with station ID, cluster membership, cluster characteristics
- **Cluster evolution** — Time-series of cluster membership changes
- **Cluster statistics** — Mean/median features per cluster (turnover, duration, e-bike share, etc.)
- **Anomaly flags** — Stations with unusual behavior (frequently full, frequently empty, high rebalancing)

#### Rebalancing recommendations
- **Recommended rebalancing** — Priority list of stations to rebalance with suggested bike counts
- **Underperforming clusters** — Clusters with high demand but low bike availability
- **Overstock stations** — Stations with excess bikes and low turnover
- **Demand hotspots** — Stations with spike in departures

## Database queries

The dashboard executes queries against the events and stations tables:

```sql
-- Trip trends (hourly)
SELECT 
  DATE_FORMAT(ts_utc, '%Y-%m-%d %H:00:00') as hour,
  COUNT(*) as trip_count,
  SUM(CASE WHEN user_type='member' THEN 1 ELSE 0 END) as member_trips,
  SUM(CASE WHEN user_type='casual' THEN 1 ELSE 0 END) as casual_trips
FROM events
WHERE type IN ('trip_started', 'trip_ended')
  AND ts_utc BETWEEN '2024-03-20 00:00:00' AND '2024-03-22 23:59:59'
GROUP BY hour
ORDER BY hour;

-- Station utilization
SELECT 
  station_id,
  COUNT(*) as total_trips,
  SUM(CASE WHEN user_type='member' THEN 1 ELSE 0 END) as member_trips,
  SUM(CASE WHEN user_type='casual' THEN 1 ELSE 0 END) as casual_trips
FROM events
WHERE type IN ('trip_started', 'trip_ended')
  AND ts_utc BETWEEN '2024-03-20' AND '2024-03-22'
GROUP BY station_id
ORDER BY total_trips DESC;
```

## Real-time MQTT subscriptions

The dashboard subscribes to MQTT topics for live updates:

```
idc/fcXX/status/<station_id>  — Station status (bikes/docks available)
```

Received messages update live occupancy gauges and status displays without requiring a database query.

## Styling and customization

Node-RED Dashboard UI can be customized via:

1. **Dashboard settings** in Node-RED editor
   - Layout (grid size, default theme)
   - Color scheme and font
   - Navigation tabs and pages

2. **CSS overrides** in custom template nodes
   - Card styling
   - Chart colors
   - Gauge thresholds and colors

3. **Angular bindings** for dynamic updates
   - Two-way data binding between UI controls and backend values
   - Conditional visibility based on selected date range

## Performance considerations

- **Query optimization:** Use indexes on `ts_utc`, `type`, `user_type`, `station_id`
- **Caching:** Store hourly/daily aggregations in cache to avoid re-computing on each refresh
- **Pagination:** Limit station utilization table to top 20 by default; allow scrolling for more
- **MQTT throttling:** Coalesce frequent status updates (e.g., 1 update per second instead of per message)
- **Dashboard refresh interval:** Default 5 seconds; configurable per visualization

## Troubleshooting

### Dashboard won't connect to database

Verify MySQL is running and accessible:
```powershell
docker compose logs database
# Check logs for startup errors, port bindings
```

Verify connection string in Node-RED database config:
```
mysql://username:password@host:3306/bike_sharing
```

### "Cannot read property 'value' of undefined"

Dashboard nodes may fail if previous nodes didn't pass data. Add debug nodes to verify data flow:
1. Connect a Debug node to each major node's output
2. Open Node-RED Debug panel (right sidebar)
3. Check actual values vs. expected

### MQTT messages not appearing

Verify subscriber is connected to Mosquitto:
```powershell
docker compose logs processor  # Check MQTT connection logs
```

Verify topic subscription matches publisher topic:
```
Expected: idc/fc10/status/JC115
Subscribed: idc/fc10/#
```

### Charts not updating on date range change

Ensure query nodes are configured to read from dashboard input widget:
1. Double-click query node
2. Verify SQL uses `msg.payload.startDate` and `msg.payload.endDate`
3. Ensure date range picker node outputs correctly formatted dates

## Related files

- `processor/__main__.py` — Subscriber that persists events to database
- `database/schema.sql` — Database schema for queries
- `mosquitto/README.md` — MQTT topic configuration
- `docker-compose.yml` — Service definition for dashboard
- `infrastructure/setup_local.py` — Credential generation for database/MQTT
- Root `README.md` — Platform overview
