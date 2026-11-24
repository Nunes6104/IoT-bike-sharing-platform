# Mosquitto

This folder configures Eclipse Mosquitto as the authenticated MQTT broker for the publisher and processor.

## TLS and topics

`config/mosquitto.conf` configures the listener on port **1883** with a CA certificate, server certificate, private key, password file, and ACL. Port 1883 is TLS in this project; there is no plaintext listener. Compose publishes the listener on the host address selected by `MQTT_BIND` (default `0.0.0.0`). QoS 1 queue limits are disabled so a temporarily slower persistent processor session does not drop queued events.

Topics include the configured two-digit group:

- `idc/fcXX/status/<station_id>`
- `idc/fcXX/trips/started`
- `idc/fcXX/trips/ended`

The publisher can write only its event topics, the processor can read them, and the health-check account is limited to its health topic. Anonymous access is disabled. Clients verify the broker certificate using `.local/certs/ca.crt`.

## Local setup

Run `python infrastructure\setup_local.py` after setting `GROUP_NUMBER` in the root `.env`. The script provisions broker credentials, ACLs, and development certificates under `.local/`; these are local secrets and must not be committed. Compose mounts the provisioned files into the container.

Check broker status with `docker compose ps mosquitto` and `docker compose logs mosquitto`. See the root [README](../README.md) for startup and Stage 2 replay commands.
