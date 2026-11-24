# Publisher

This package implements Client 1: a publisher that replays the supplied Stage 2 JSONL event stream to the configured MQTT topics.

## Behavior

- Validates each source record and routes `station_status`, `trip_started`, and `trip_ended` events to the configured `idc/fcXX/...` topic.
- Uses the source timestamps to preserve relative inter-message intervals, divided by `REPLAY_SPEED`.
- Publishes with QoS 1 over TLS and validates the broker certificate against the configured CA.
- Persists a checkpoint after each batch of 100 broker-acknowledged messages and at end of file. A crash can replay up to 99 already-acknowledged events; the processor uses idempotent event keys.

The source payload is passed through without inventing fields. Topic and station consistency are checked before publishing.

## Run with Compose

Set `GROUP_NUMBER` and `REPLAY_SPEED` in the root `.env`, then run:

```powershell
docker compose --profile replay run --build --rm publisher
```

The publisher container waits for the processor and broker health checks. Its checkpoint is stored in the Compose `publisher_checkpoint` volume. To intentionally replace that checkpoint and restart from the first line:

```powershell
docker compose --profile replay run --rm --entrypoint python publisher -m publisher --reset
```

The checkpoint is bound to the dataset contents, group, and speed. See the root [README](../README.md) for first-time setup and integration details.
