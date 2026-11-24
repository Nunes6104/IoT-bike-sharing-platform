"""Replay the online Stage 2 event file to Mosquitto."""

import argparse
import logging
import os
import sys
from pathlib import Path

from publisher.replay import DEFAULT_CHECKPOINT, create_mqtt_publisher, replay_file


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(os.environ.get(
            "DATA_PATH", str(ROOT / "dataset-IdC-2627" / "stage2_online.jsonl")
        )),
    )
    parser.add_argument(
        "--stations",
        type=Path,
        default=Path(os.environ.get(
            "STATIONS_PATH", str(ROOT / "dataset-IdC-2627" / "stations.json")
        )),
    )
    parser.add_argument("--group", default=os.environ.get("GROUP_NUMBER"))
    parser.add_argument("--speed", type=float, default=float(os.environ.get("REPLAY_SPEED", "1")))
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(os.environ.get("REPLAY_CHECKPOINT", str(DEFAULT_CHECKPOINT))),
    )
    parser.add_argument("--reset", action="store_true", help="start from line 1 and replace checkpoint")
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST", "mosquitto"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.environ.get("MQTT_USERNAME", "publisher"))
    parser.add_argument(
        "--password-file",
        type=Path,
        default=Path(os.environ.get(
            "MQTT_PASSWORD_FILE", str(ROOT / ".local" / "mosquitto" / "publisher.password")
        )),
    )
    parser.add_argument(
        "--ca-cert",
        type=Path,
        default=Path(os.environ.get("MQTT_CA_CERT", str(ROOT / ".local" / "certs" / "ca.crt"))),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.group:
        parser.error("--group or GROUP_NUMBER is required")
    if not args.data.is_file() or not args.stations.is_file():
        parser.error("event data and station reference files must exist")
    if not args.ca_cert.is_file():
        parser.error("a trusted MQTT CA certificate is required")

    publisher = None
    try:
        password_path = Path(os.environ.get("MQTT_PASSWORD_FILE", args.password_file))
        password = password_path.read_text(encoding="utf-8").strip()
        if not password:
            raise ValueError(f"MQTT password file is empty: {args.password_file}")
        publish_and_wait, publisher = create_mqtt_publisher(
            args.host, args.port, args.username, password, args.ca_cert
        )
        count = replay_file(
            args.data,
            args.stations,
            args.group,
            args.speed,
            args.checkpoint,
            publish_and_wait,
            reset=args.reset,
        )
        logging.info("Replay finished; acknowledged %d newly published messages", count)
        return 0
    except (OSError, ValueError, ConnectionError, TimeoutError) as exc:
        logging.error("Replay failed: %s", exc)
        return 2
    finally:
        if publisher is not None:
            publisher()


if __name__ == "__main__":
    sys.exit(main())
