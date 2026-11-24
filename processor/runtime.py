"""Run the MQTT consumer and HTTPS analytics API within the processor service."""

import logging
import signal
import threading
from pathlib import Path

from processor.api import create_server
from processor.config import database_url_from_env
from processor.db import apply_schema, create_secure_connection
from processor.event_store import EventStore
from processor.subscriber import run_subscriber
from processor.validation import load_station_ids


LOGGER = logging.getLogger("processor.runtime")


def run(
    *,
    stations_path: Path,
    schema_path: Path,
    database_url: str | None,
    ca_file: Path,
    group_number: str,
    mqtt_host: str,
    mqtt_port: int,
    mqtt_username: str,
    mqtt_password_file: Path,
    ready_file: Path,
    api_token_file: Path,
    api_certificate: Path,
    api_private_key: Path,
    api_host: str,
    api_port: int,
) -> None:
    """Bootstrap shared persistence, then manage API and MQTT subscriber lifecycles."""
    engine = create_secure_connection(database_url or database_url_from_env(), ca_file)
    apply_schema(engine, schema_path)
    station_ids = load_station_ids(stations_path)
    EventStore(engine, station_ids).load_stations(stations_path)
    api_server = create_server(
        engine, api_token_file, api_certificate, api_private_key, api_host, api_port
    )
    shutdown = threading.Event()
    failures: list[BaseException] = []

    def run_api() -> None:
        try:
            api_server.serve_forever(poll_interval=0.5)
        except BaseException as exc:
            failures.append(exc)
            shutdown.set()
        finally:
            api_server.ready_event.set()

    def run_mqtt() -> None:
        try:
            password = mqtt_password_file.read_text(encoding="utf-8").strip()
            if not password:
                raise ValueError(f"MQTT password file is empty: {mqtt_password_file}")
            run_subscriber(
                engine,
                station_ids,
                broker_host=mqtt_host,
                broker_port=mqtt_port,
                group_number=group_number,
                username=mqtt_username,
                password=password,
                ca_file=ca_file,
                ready_file=ready_file,
                stop_event=shutdown,
            )
        except BaseException as exc:
            failures.append(exc)
            shutdown.set()
            if api_server.is_serving:
                api_server.shutdown()

    api_thread = threading.Thread(target=run_api, name="analytics-api", daemon=True)
    api_thread.start()
    if not api_server.ready_event.wait(timeout=10):
        raise RuntimeError("analytics API failed to start")
    if shutdown.is_set():
        raise RuntimeError("analytics API failed to start") from (failures[0] if failures else None)

    mqtt_thread = threading.Thread(target=run_mqtt, name="mqtt-subscriber", daemon=True)
    mqtt_thread.start()

    previous_sigterm = signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    previous_sigint = signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    LOGGER.info("Processor service started; waiting for shutdown or a service failure")
    try:
        shutdown.wait()
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)
        shutdown.set()
        if api_server.is_serving:
            api_server.shutdown()
        api_server.server_close()
        mqtt_thread.join(timeout=10)
        api_thread.join(timeout=10)
        engine.dispose()
    if failures:
        raise RuntimeError("processor background service failed") from failures[0]
