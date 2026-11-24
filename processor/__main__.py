"""Processor commands for offline loading, MQTT ingestion, and analytics API."""

import argparse
import logging
import os
import sys
from pathlib import Path

from processor.config import database_url_from_env, mqtt_password_from_env
from processor.db import apply_schema, create_secure_connection
from processor.offline_loader import OfflineLoader
from processor.subscriber import run_subscriber
from processor.validation import load_station_ids


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "database" / "schema.sql"


def _engine(db_url: str | None, ca_cert: Path):
    return create_secure_connection(db_url or database_url_from_env(), ca_cert)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="processor",
        description="Load and process bike-sharing events",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    offline = commands.add_parser("load-offline", help="load offline JSONL files")
    offline.add_argument("--stations", type=Path, required=True)
    offline.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    offline.add_argument("--ca-cert", type=Path, default=Path(os.environ.get(
        "DB_CA_CERT", "/run/bike-certs/ca.crt"
    )))
    offline.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    offline.add_argument("--dry-run", action="store_true")
    offline.add_argument("files", type=Path, nargs="+")

    subscriber = commands.add_parser("subscribe", help="consume MQTT events")
    subscriber.add_argument("--stations", type=Path, default=Path(os.environ.get(
        "STATIONS_PATH", str(ROOT / "dataset-IdC-2627" / "stations.json")
    )))
    subscriber.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    subscriber.add_argument("--ca-cert", type=Path, default=Path(os.environ.get(
        "DB_CA_CERT", "/run/bike-certs/ca.crt"
    )))
    subscriber.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    subscriber.add_argument("--group", default=os.environ.get("GROUP_NUMBER"))
    subscriber.add_argument("--broker-host", default=os.environ.get("MQTT_HOST", "mosquitto"))
    subscriber.add_argument("--broker-port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    subscriber.add_argument("--mqtt-username", default=os.environ.get("MQTT_USERNAME", "processor"))
    subscriber.add_argument("--mqtt-password-file", type=Path, default=Path(os.environ.get(
        "MQTT_PASSWORD_FILE", "/run/bike-mqtt/processor.password"
    )))
    subscriber.add_argument("--ready-file", type=Path, default=Path(
        os.environ.get("PROCESSOR_READY_FILE", "/tmp/processor-ready")
    ))

    api = commands.add_parser("api", help="serve the HTTPS analytics API")
    api.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    api.add_argument("--ca-cert", type=Path, default=Path(os.environ.get(
        "DB_CA_CERT", "/run/bike-certs/ca.crt"
    )))
    api.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    api.add_argument("--token-file", type=Path, default=Path(os.environ.get(
        "ANALYTICS_TOKEN_FILE", "/run/bike-processor/analytics.token"
    )))
    api.add_argument("--certificate", type=Path, default=Path(os.environ.get(
        "API_CERT_FILE", "/run/bike-certs/server.crt"
    )))
    api.add_argument("--private-key", type=Path, default=Path(os.environ.get(
        "API_KEY_FILE", "/run/bike-certs/server.key"
    )))
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8443)

    runtime = commands.add_parser("run", help="run MQTT ingestion and HTTPS analytics API")
    runtime.add_argument("--stations", type=Path, default=Path(os.environ.get(
        "STATIONS_PATH", str(ROOT / "dataset-IdC-2627" / "stations.json")
    )))
    runtime.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    runtime.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    runtime.add_argument("--ca-cert", type=Path, default=Path(os.environ.get(
        "DB_CA_CERT", "/run/bike-certs/ca.crt"
    )))
    runtime.add_argument("--group", default=os.environ.get("GROUP_NUMBER"))
    runtime.add_argument("--broker-host", default=os.environ.get("MQTT_HOST", "mosquitto"))
    runtime.add_argument("--broker-port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    runtime.add_argument("--mqtt-username", default=os.environ.get("MQTT_USERNAME", "processor"))
    runtime.add_argument("--mqtt-password-file", type=Path, default=Path(os.environ.get(
        "MQTT_PASSWORD_FILE", "/run/bike-mqtt/processor.password"
    )))
    runtime.add_argument("--ready-file", type=Path, default=Path(
        os.environ.get("PROCESSOR_READY_FILE", "/tmp/processor-ready")
    ))
    runtime.add_argument("--api-token-file", type=Path, default=Path(os.environ.get(
        "ANALYTICS_TOKEN_FILE", "/run/bike-processor/analytics.token"
    )))
    runtime.add_argument("--api-certificate", type=Path, default=Path(os.environ.get(
        "API_CERT_FILE", "/run/bike-certs/server.crt"
    )))
    runtime.add_argument("--api-private-key", type=Path, default=Path(os.environ.get(
        "API_KEY_FILE", "/run/bike-certs/server.key"
    )))
    runtime.add_argument("--api-host", default="0.0.0.0")
    runtime.add_argument("--api-port", type=int, default=8443)

    args = parser.parse_args()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        if args.command == "load-offline":
            engine = create_secure_connection(
                args.db_url or database_url_from_env(), args.ca_cert
            )
            apply_schema(engine, args.schema)
            station_ids = load_station_ids(args.stations)
            loader = OfflineLoader(engine, dry_run=args.dry_run)
            station_result = loader.load_stations(args.stations)
            if station_result != 0:
                return station_result
            for path in args.files:
                loader.load_events(path, station_ids)
            return loader.report()

        engine = _engine(args.db_url, args.ca_cert)
        apply_schema(engine, args.schema)

        if args.command == "subscribe":
            if not args.group:
                raise ValueError("GROUP_NUMBER or --group is required")
            station_ids = load_station_ids(args.stations)
            run_subscriber(
                engine,
                station_ids,
                broker_host=args.broker_host,
                broker_port=args.broker_port,
                group_number=args.group,
                username=args.mqtt_username,
                password=mqtt_password_from_env(),
                ca_file=args.ca_cert,
                ready_file=args.ready_file,
            )
            return 0

        if args.command == "run":
            if not args.group:
                raise ValueError("GROUP_NUMBER or --group is required")
            from processor.runtime import run as run_processor

            run_processor(
                stations_path=args.stations,
                schema_path=args.schema,
                database_url=args.db_url,
                ca_file=args.ca_cert,
                group_number=args.group,
                mqtt_host=args.broker_host,
                mqtt_port=args.broker_port,
                mqtt_username=args.mqtt_username,
                mqtt_password_file=args.mqtt_password_file,
                ready_file=args.ready_file,
                api_token_file=args.api_token_file,
                api_certificate=args.api_certificate,
                api_private_key=args.api_private_key,
                api_host=args.api_host,
                api_port=args.api_port,
            )
            return 0

        from processor.api import serve

        serve(
            engine,
            args.token_file,
            args.certificate,
            args.private_key,
            host=args.host,
            port=args.port,
        )
        return 0
    except KeyboardInterrupt:
        logging.info("Shutdown requested")
        return 130
    except Exception as exc:
        logging.error("%s command failed: %s", args.command, exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
