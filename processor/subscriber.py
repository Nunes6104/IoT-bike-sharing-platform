"""MQTT subscriber that commits or quarantines each event before acknowledging it."""

import logging
import ssl
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from processor.event_store import EventStore
from processor.validation import Issue, parse_json_record


LOGGER = logging.getLogger("processor.subscriber")


def expected_topic(group_number: str, event: dict[str, Any]) -> str | None:
    """Return the sole permitted group topic for an event payload."""
    prefix = f"idc/fc{group_number}"
    if event.get("type") == "station_status" and isinstance(event.get("station_id"), str):
        return f"{prefix}/status/{event['station_id']}"
    if event.get("type") == "trip_started":
        return f"{prefix}/trips/started"
    if event.get("type") == "trip_ended":
        return f"{prefix}/trips/ended"
    return None


def validate_topic_event(topic: str, group_number: str, event: dict[str, Any]) -> list[Issue]:
    """Require the MQTT topic's group and event routing to match the payload."""
    expected = expected_topic(group_number, event)
    if expected is None or topic != expected:
        return [Issue("error", "topic", "MQTT topic does not match event type or station identifier")]
    return []


def run_subscriber(
    engine: Engine,
    station_ids: set[str],
    *,
    broker_host: str,
    broker_port: int,
    group_number: str,
    username: str,
    password: str,
    ca_file: Path,
    ready_file: Path,
    stop_event: threading.Event | None = None,
) -> None:
    """Connect with verified TLS, use a persistent QoS 1 session, and manual ACKs."""
    import paho.mqtt.client as mqtt

    if len(group_number) != 2 or not group_number.isdigit():
        raise ValueError("group number must contain exactly two digits")
    if not ca_file.is_file():
        raise ValueError(f"MQTT CA certificate not found: {ca_file}")

    event_store = EventStore(engine, station_ids)
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"bike-processor-{group_number}",
        protocol=mqtt.MQTTv311,
        clean_session=False,
        manual_ack=True,
    )
    client.username_pw_set(username, password)
    tls_context = ssl.create_default_context(cafile=str(ca_file))
    tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    client.tls_set_context(tls_context)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client_instance, userdata, flags, reason_code, properties):
        if reason_code != 0:
            LOGGER.error("MQTT connection rejected: %s", reason_code)
            return
        topics = [
            (f"idc/fc{group_number}/status/+", 1),
            (f"idc/fc{group_number}/trips/started", 1),
            (f"idc/fc{group_number}/trips/ended", 1),
        ]
        result, _ = client_instance.subscribe(topics)
        if result != mqtt.MQTT_ERR_SUCCESS:
            LOGGER.error("MQTT subscribe request failed: %s", result)

    def on_subscribe(client_instance, userdata, mid, reason_code_list, properties):
        if any(reason_code.is_failure for reason_code in reason_code_list):
            LOGGER.error("Broker rejected one or more MQTT subscriptions")
            return
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_text("ready\n", encoding="ascii")
        LOGGER.info("MQTT subscriptions are active")

    def on_disconnect(client_instance, userdata, disconnect_flags, reason_code, properties):
        try:
            ready_file.unlink(missing_ok=True)
        except OSError:
            LOGGER.exception("Unable to clear subscriber readiness marker")
        if reason_code != 0:
            LOGGER.warning("MQTT disconnected: %s", reason_code)

    def on_message(client_instance, userdata, message):
        payload = bytes(message.payload)
        try:
            try:
                event = parse_json_record(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError):
                disposition = event_store.ingest(
                    payload, source="mqtt", topic=message.topic
                )
            else:
                route_issues = validate_topic_event(
                    message.topic, group_number, event
                )
                if route_issues:
                    event_store.quarantine_payload(
                        payload,
                        source="mqtt",
                        topic=message.topic,
                        issues=route_issues,
                    )
                    disposition = "rejected"
                else:
                    disposition = event_store.ingest(
                        payload, source="mqtt", topic=message.topic
                    )
            if disposition in ("rejected", "conflict"):
                LOGGER.warning("MQTT message disposition=%s topic=%s", disposition, message.topic)
            ack_result = client_instance.ack(message.mid, message.qos)
            if ack_result != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT acknowledgment failed: {ack_result}")
        except Exception:
            LOGGER.exception(
                "MQTT message processing failed; leaving message unacknowledged"
            )
            client_instance.disconnect()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    shutdown = stop_event or threading.Event()
    client.connect_async(broker_host, broker_port, keepalive=60)
    client.loop_start()
    try:
        while not shutdown.wait(1):
            pass
    finally:
        try:
            ready_file.unlink(missing_ok=True)
        except OSError:
            LOGGER.exception("Unable to clear subscriber readiness marker")
        client.disconnect()
        client.loop_stop()

