"""Replay Stage 2 JSONL events over verified MQTT/TLS with durable checkpoints."""

import hashlib
import json
import logging
import os
import ssl
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from processor.validation import load_station_ids, parse_json_record, parse_source_timestamp, validate_event


LOGGER = logging.getLogger("publisher.replay")
DEFAULT_CHECKPOINT = Path(".local/publisher/stage2.checkpoint.json")
CHECKPOINT_INTERVAL = 100


def event_topic(event: dict, group_number: str) -> str:
    """Map a validated event to its single group-specific MQTT topic."""
    prefix = f"idc/fc{group_number}"
    if event.get("type") == "station_status":
        return f"{prefix}/status/{event['station_id']}"
    if event.get("type") == "trip_started":
        return f"{prefix}/trips/started"
    if event.get("type") == "trip_ended":
        return f"{prefix}/trips/ended"
    raise ValueError(f"unsupported event type: {event.get('type')!r}")


def dataset_digest(path: Path) -> str:
    """Hash a file in bounded memory for checkpoint identity."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_checkpoint(
    path: Path,
    file_digest: str,
    group_number: str,
    speed: float,
    reset: bool = False,
) -> dict:
    """Load a compatible replay checkpoint or initialize an empty one."""
    if reset and path.exists():
        path.unlink()
    if not path.exists():
        return {
            "version": 1,
            "dataset_sha256": file_digest,
            "group_number": group_number,
            "speed": speed,
            "next_line": 1,
            "last_timestamp": None,
        }
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "version": 1,
        "dataset_sha256": file_digest,
        "group_number": group_number,
        "speed": speed,
    }
    if any(checkpoint.get(key) != value for key, value in expected.items()):
        raise ValueError("checkpoint belongs to a different dataset or replay configuration")
    if not isinstance(checkpoint.get("next_line"), int) or checkpoint["next_line"] < 1:
        raise ValueError("checkpoint next_line is invalid")
    return checkpoint


def save_checkpoint(path: Path, checkpoint: dict) -> None:
    """Atomically persist the next line only after its broker acknowledgment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as destination:
        json.dump(checkpoint, destination, sort_keys=True)
        destination.write("\n")
        destination.flush()
        os.fsync(destination.fileno())
    try:
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _wait_for_ack(receipt: object | None) -> None:
    """Wait for a broker acknowledgment when the publisher returns one."""
    if receipt is None:
        return
    wait = getattr(receipt, "wait_for_publish", None)
    is_published = getattr(receipt, "is_published", None)
    if not callable(wait) or not callable(is_published):
        raise TypeError("publish callback must return None or an MQTT publish receipt")
    wait(timeout=60)
    if not is_published():
        raise TimeoutError("MQTT QoS 1 acknowledgment timed out")


def replay_file(
    path: Path,
    stations_path: Path,
    group_number: str,
    speed: float,
    checkpoint_path: Path,
    publish_and_wait: Callable[[str, bytes], object | None],
    *,
    reset: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Publish a validated stream in source-time order and checkpoint QoS ACKs."""
    if len(group_number) != 2 or not group_number.isdigit():
        raise ValueError("group number must contain exactly two digits")
    if speed <= 0:
        raise ValueError("replay speed must be positive")
    station_ids = load_station_ids(stations_path)
    file_digest = dataset_digest(path)
    checkpoint = load_checkpoint(checkpoint_path, file_digest, group_number, speed, reset)
    previous_timestamp = (
        parse_source_timestamp(checkpoint["last_timestamp"])
        if checkpoint["last_timestamp"] else None
    )
    deadline = clock()
    published = 0
    pending: list[tuple[int, datetime, object | None]] = []

    def acknowledge_batch() -> None:
        nonlocal published
        if not pending:
            return
        for _, _, receipt in pending:
            _wait_for_ack(receipt)
        line_number, timestamp, _ = pending[-1]
        checkpoint.update({
            "next_line": line_number + 1,
            "last_timestamp": timestamp.isoformat(),
        })
        save_checkpoint(checkpoint_path, checkpoint)
        published += len(pending)
        pending.clear()

    with path.open("rb") as source:
        for line_number, raw_line in enumerate(source, 1):
            if line_number < checkpoint["next_line"]:
                continue
            payload = raw_line.rstrip(b"\r\n")
            try:
                event = parse_json_record(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError) as exc:
                raise ValueError(f"invalid JSON at line {line_number}: {exc}") from exc
            issues = validate_event(event, station_ids)
            if any(issue.severity == "error" for issue in issues):
                raise ValueError(f"invalid event at line {line_number}: {issues}")

            timestamp = parse_source_timestamp(event["ts"])
            if previous_timestamp is not None:
                interval = (timestamp - previous_timestamp).total_seconds()
                if interval < 0:
                    raise ValueError(f"source timestamp moved backwards at line {line_number}")
                deadline += interval / speed
                delay = deadline - clock()
                if delay > 0:
                    sleep(delay)

            receipt = publish_and_wait(event_topic(event, group_number), payload)
            pending.append((line_number, timestamp, receipt))
            if len(pending) >= CHECKPOINT_INTERVAL:
                acknowledge_batch()
            previous_timestamp = timestamp
    acknowledge_batch()
    return published


def create_mqtt_publisher(
    host: str,
    port: int,
    username: str,
    password: str,
    ca_file: Path,
) -> tuple[Callable[[str, bytes], None], Callable[[], None]]:
    """Connect Paho with CA and hostname verification and return publish/close calls."""
    import paho.mqtt.client as mqtt

    connected = threading.Event()
    connection_error: list[str] = []
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"bike-publisher-{os.getpid()}",
        protocol=mqtt.MQTTv311,
        clean_session=True,
    )
    client.username_pw_set(username, password)
    context = ssl.create_default_context(cafile=str(ca_file))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    client.tls_set_context(context)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client_instance, userdata, flags, reason_code, properties):
        if reason_code == 0:
            connected.set()
        else:
            connection_error.append(str(reason_code))

    def on_connect_fail(client_instance, userdata):
        LOGGER.warning("MQTT connection attempt failed")

    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.connect_async(host, port, keepalive=60)
    client.loop_start()
    if not connected.wait(timeout=60):
        client.loop_stop()
        client.disconnect()
        detail = connection_error[-1] if connection_error else "connection timed out"
        raise ConnectionError(f"cannot connect to MQTT broker: {detail}")

    def publish(topic: str, payload: bytes):
        result = client.publish(topic, payload, qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT publish failed for {topic}: {result.rc}")
        return result

    def close() -> None:
        client.disconnect()
        client.loop_stop()

    return publish, close
