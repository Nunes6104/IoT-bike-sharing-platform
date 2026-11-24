# Dashboard

This folder contains the Node-RED configuration for Client 2, the operator-facing historical analytics page.

## Files and data flow

- `flows.json` serves `/bike-sharing` and proxies `/api/analytics` requests.
- `settings.js` enables HTTPS, editor and HTTP-flow authentication, and loads the analytics token from a mounted secret.
- The page calls the processor API over HTTPS; Node-RED verifies the processor certificate through `NODE_EXTRA_CA_CERTS`. It does not connect directly to MySQL or MQTT.

The page provides configurable local start/end times and hourly, daily, or weekly trip trends; member/casual trip counts; average duration; estimated fares and e-bike energy; time-of-day totals; and station arrivals/departures plus empty/full observed-update counts. The end time is exclusive. Status gaps are not treated as empty stations, and unavailable energy is labeled rather than set to zero.

Live active-trip displays, clusters, anomaly detection, and rebalancing recommendations are not implemented. The ML container is separate and currently a placeholder.

## Run

Provision local certificates and secrets, then start Compose. Open **https://localhost:1880/bike-sharing** and authenticate with user `admin`; the generated password is stored in `.local/dashboard/admin.password`. Trust `.local/certs/ca.crt` in the browser for the local development certificate.

The Node-RED editor uses the same HTTPS endpoint on port 1880. See the root [README](../README.md) for service startup and data loading.
