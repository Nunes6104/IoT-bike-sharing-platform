"""Offline stage 1 event loader: imports stations and events into MySQL with idempotent keying."""

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from processor.validation import Issue, load_station_ids, parse_json_record, parse_source_timestamp, validate_event


def utc_from_source_time(source_ts: datetime) -> datetime:
    """Convert source timestamp (with explicit -04:00 offset) to UTC."""
    if source_ts.tzinfo is None:
        raise ValueError("source timestamp must be timezone-aware")
    utc_ts = source_ts.astimezone(timezone.utc)
    return utc_ts.replace(tzinfo=None)


def content_hash(payload: dict) -> str:
    """Compute SHA-256 hash of JSON payload (canonicalized)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class OfflineLoader:
    """Load stage 1 offline dataset into MySQL with validation and idempotent keying."""

    def __init__(self, engine: Engine, dry_run: bool = False):
        self.engine = engine
        self.dry_run = dry_run
        self.stats = Counter()
        self.conflicts = []

    def load_stations(self, path: Path) -> int:
        """Load and store station reference data."""
        try:
            station_ids = load_station_ids(path)
        except (OSError, ValueError) as exc:
            print(f"Cannot load stations from {path}: {exc}", file=sys.stderr)
            return 2

        with self.engine.connect() as conn:
            if self.engine.dialect.name == 'mysql':
                conn.execute(text("SET SESSION time_zone='+00:00'"))
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
                for station in data:
                    station_id = station['station_id']
                    payload_json = json.dumps(station, ensure_ascii=True)
                    if not self.dry_run:
                        conn.execute(
                            text(
                                "INSERT INTO stations (station_id, payload) VALUES (:id, :payload) "
                                "ON DUPLICATE KEY UPDATE payload = :payload"
                            ),
                            {"id": station_id, "payload": payload_json}
                        )
                    self.stats['stations_loaded'] += 1
                conn.commit()
            except SQLAlchemyError as exc:
                print(f"Database error loading stations: {exc}", file=sys.stderr)
                return 2
        return 0

    def load_events(self, path: Path, station_ids: set[str]) -> None:
        """Load events from JSONL file, persisting valid/warning records and quarantining errors."""
        with path.open(encoding='utf-8-sig') as source:
            with self.engine.connect() as conn:
                if self.engine.dialect.name == 'mysql':
                    conn.execute(text("SET SESSION time_zone='+00:00'"))
                for line_number, line in enumerate(source, 1):
                    self.stats['records_read'] += 1
                    try:
                        event = parse_json_record(line)
                    except (ValueError, RecursionError) as exc:
                        if not self.dry_run:
                            self._quarantine_line(conn, path, line_number, line.rstrip('\r\n'),
                                                  [Issue('error', 'json', str(exc))])
                        self.stats['records_rejected'] += 1
                        self.stats['errors'] += 1
                        continue

                    issues = validate_event(event, station_ids)
                    if any(issue.severity == 'error' for issue in issues):
                        if not self.dry_run:
                            self._quarantine_line(conn, path, line_number, line.rstrip('\r\n'), issues)
                        self.stats['records_rejected'] += 1
                        self.stats['errors'] += 1
                        continue

                    has_warnings = any(issue.severity == 'warning' for issue in issues)
                    if not self.dry_run:
                        self._store_event(conn, event, issues, line_number)
                    self.stats['records_processed'] += 1
                    if has_warnings:
                        self.stats['records_with_warnings'] += 1
                try:
                    conn.commit()
                except SQLAlchemyError as exc:
                    print(f"Database error during event load: {exc}", file=sys.stderr)
                    raise

    def _quarantine_line(self, conn, path: Path, line_number: int, raw_text: str,
                         issues: list[Issue]) -> None:
        """Store a rejected line in the rejected_lines table."""
        try:
            if self.engine.dialect.name == 'mysql':
                conn.execute(
                    text(
                        "INSERT INTO rejected_lines (source_path, line_number, raw_text, issues) "
                        "VALUES (:path, :line, :raw, :issues) "
                        "ON DUPLICATE KEY UPDATE issues = :issues"
                    ),
                    {
                        'path': str(path),
                        'line': line_number,
                        'raw': raw_text,
                        'issues': json.dumps([{'severity': i.severity, 'field': i.field, 'message': i.message}
                                              for i in issues], ensure_ascii=True),
                    }
                )
            else:  # SQLite
                conn.execute(
                    text(
                        "INSERT OR REPLACE INTO rejected_lines (source_path, line_number, raw_text, issues) "
                        "VALUES (:path, :line, :raw, :issues)"
                    ),
                    {
                        'path': str(path),
                        'line': line_number,
                        'raw': raw_text,
                        'issues': json.dumps([{'severity': i.severity, 'field': i.field, 'message': i.message}
                                              for i in issues], ensure_ascii=True),
                    }
                )
        except SQLAlchemyError as exc:
            print(f"Database error quarantining line {line_number}: {exc}", file=sys.stderr)

    def _store_event(self, conn, event: dict[str, Any], issues: list[Issue], line_number: int) -> None:
        """Store a valid or warning-bearing event, detecting conflicts on key collision."""
        seq = event['seq']
        event_type = event['type']
        payload_json = json.dumps(event, ensure_ascii=True)

        try:
            ts_utc = utc_from_source_time(parse_source_timestamp(event['ts']))
        except ValueError:
            self.stats['timestamp_errors'] += 1
            return

        try:
            if self.engine.dialect.name == 'mysql':
                conn.execute(
                    text(
                        "INSERT INTO events (seq, type, ts_utc, payload, validation_status, validation_reason, source_line_number) "
                        "VALUES (:seq, :type, :ts_utc, :payload, :status, :reason, :line) "
                        "ON DUPLICATE KEY UPDATE payload=IF(payload=:payload, payload, :payload), "
                        "validation_reason=:reason"
                    ),
                    {
                        'seq': seq,
                        'type': event_type,
                        'ts_utc': ts_utc,
                        'payload': payload_json,
                        'status': 'warning' if issues else 'valid',
                        'reason': json.dumps([{'severity': i.severity, 'field': i.field, 'message': i.message}
                                              for i in issues], ensure_ascii=True) if issues else None,
                        'line': line_number,
                    }
                )
            else:  # SQLite
                conn.execute(
                    text(
                        "INSERT OR REPLACE INTO events (seq, type, ts_utc, payload, validation_status, validation_reason, source_line_number) "
                        "VALUES (:seq, :type, :ts_utc, :payload, :status, :reason, :line)"
                    ),
                    {
                        'seq': seq,
                        'type': event_type,
                        'ts_utc': ts_utc,
                        'payload': payload_json,
                        'status': 'warning' if issues else 'valid',
                        'reason': json.dumps([{'severity': i.severity, 'field': i.field, 'message': i.message}
                                              for i in issues], ensure_ascii=True) if issues else None,
                        'line': line_number,
                    }
                )
        except SQLAlchemyError as exc:
            print(f"Database error storing event seq={seq}: {exc}", file=sys.stderr)

    def report(self) -> int:
        """Print summary and return exit code."""
        print(json.dumps({
            'stations_loaded': self.stats['stations_loaded'],
            'records_read': self.stats['records_read'],
            'records_processed': self.stats['records_processed'],
            'records_with_warnings': self.stats['records_with_warnings'],
            'records_rejected': self.stats['records_rejected'],
            'errors': self.stats['errors'],
        }, ensure_ascii=True), file=sys.stderr)

        exit_code = 1 if self.stats['errors'] > 0 else 0
        return exit_code
