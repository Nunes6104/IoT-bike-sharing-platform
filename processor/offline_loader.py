"""Offline stage 1 event loader using the shared validated event store."""

import json
import sys
from collections import Counter
from contextlib import nullcontext
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from processor.event_store import EventStore, content_hash, utc_from_source_time
from processor.validation import load_station_ids, parse_json_record, validate_event


class OfflineLoader:
    """Load station and event JSONL data without overwriting conflicting sequences."""

    def __init__(self, engine: Engine, dry_run: bool = False):
        self.engine = engine
        self.dry_run = dry_run
        self.stats: Counter[str] = Counter()
        self.store: EventStore | None = None

    def load_stations(self, path: Path) -> int:
        """Validate and load station reference data."""
        try:
            station_ids = load_station_ids(path)
            self.store = EventStore(self.engine, station_ids)
            self.stats["stations_loaded"] = (
                len(station_ids) if self.dry_run else self.store.load_stations(path)
            )
        except (OSError, ValueError) as exc:
            print(f"Cannot load stations from {path}: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"Database error loading stations: {exc}", file=sys.stderr)
            return 2
        return 0

    def load_events(self, path: Path, station_ids: set[str]) -> None:
        """Stream JSONL records and persist each event or its quarantine record."""
        store = self.store or EventStore(self.engine, station_ids)
        connection_context = (
            nullcontext(None) if self.dry_run else self.engine.connect()
        )
        with connection_context as connection:
            if connection is not None and self.engine.dialect.name == "mysql":
                connection.execute(text("SET SESSION time_zone='+00:00'"))
            with path.open(encoding="utf-8-sig", newline="") as source:
                for line_number, line in enumerate(source, 1):
                    self.stats["records_read"] += 1
                    if self.dry_run:
                        disposition = self._validate_only(line, station_ids)
                    else:
                        disposition = store.ingest(
                            line.encode("utf-8"),
                            source="offline",
                            source_path=str(path),
                            line_number=line_number,
                            connection=connection,
                        )
                    self.stats["records_processed"] += disposition != "rejected"
                    self.stats["records_rejected"] += disposition == "rejected"
                    self.stats["records_with_warnings"] += disposition == "warning"
                    self.stats["duplicates"] += disposition == "duplicate"
                    self.stats["conflicts"] += disposition == "conflict"
                    self.stats["errors"] += disposition in ("rejected", "conflict")
                    if connection is not None and self.stats["records_read"] % 500 == 0:
                        connection.commit()
            if connection is not None:
                connection.commit()

    @staticmethod
    def _validate_only(line: str, station_ids: set[str]) -> str:
        try:
            event = parse_json_record(line)
        except (ValueError, RecursionError):
            return "rejected"
        issues = validate_event(event, station_ids)
        if any(issue.severity == "error" for issue in issues):
            return "rejected"
        return "warning" if issues else "stored"

    def report(self) -> int:
        """Print a stable JSON summary and return a nonzero code on data errors."""
        print(json.dumps({
            "stations_loaded": self.stats["stations_loaded"],
            "records_read": self.stats["records_read"],
            "records_processed": self.stats["records_processed"],
            "records_with_warnings": self.stats["records_with_warnings"],
            "records_rejected": self.stats["records_rejected"],
            "duplicates": self.stats["duplicates"],
            "conflicts": self.stats["conflicts"],
            "errors": self.stats["errors"],
        }, ensure_ascii=True), file=sys.stderr)
        return 1 if self.stats["errors"] else 0
