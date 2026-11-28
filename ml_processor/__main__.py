"""Entrypoint for the standalone station-profiling service."""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from threading import Event

from sqlalchemy import text

from ml_processor.profiles import refresh_interval_seconds, refresh_profiles
from processor.config import database_url_from_env
from processor.db import apply_schema, create_secure_connection


ROOT = Path(__file__).resolve().parents[1]
STOP = Event()
LOGGER = logging.getLogger("ml_processor")


def _engine():
    return create_secure_connection(
        database_url_from_env(),
        Path(os.environ.get("DB_CA_CERT", "/run/bike-certs/ca.crt")),
    )


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine = _engine()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "healthcheck":
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM ml_models LIMIT 1"))
            return 0

        apply_schema(engine, ROOT / "database" / "schema.sql")
        interval = refresh_interval_seconds()
        signal.signal(signal.SIGTERM, lambda _signum, _frame: STOP.set())
        signal.signal(signal.SIGINT, lambda _signum, _frame: STOP.set())
        while not STOP.is_set():
            try:
                refresh_profiles(engine)
            except Exception:
                LOGGER.exception("Station profile refresh failed; retrying")
            STOP.wait(interval)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
