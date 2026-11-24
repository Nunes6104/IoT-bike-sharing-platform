"""Validated, idempotent event persistence shared by file and MQTT ingestion."""

import base64
from contextlib import nullcontext
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from processor.validation import Issue, parse_json_record, parse_source_timestamp, validate_event


def utc_from_source_time(source_ts: datetime) -> datetime:
    """Convert an explicitly offset source timestamp to a naive UTC database value."""
    if source_ts.tzinfo is None:
        raise ValueError("source timestamp must be timezone-aware")
    return source_ts.astimezone(timezone.utc).replace(tzinfo=None)


def content_hash(payload: dict[str, Any]) -> str:
    """Hash canonical JSON so key ordering and whitespace do not affect identity."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EventStore:
    """Persist validated events without overwriting an existing sequence."""

    def __init__(self, engine: Engine, station_ids: set[str]):
        self.engine = engine
        self.station_ids = station_ids

    def load_stations(self, path: Path) -> int:
        """Insert or update station reference payloads."""
        stations = json.loads(path.read_text(encoding="utf-8-sig"))
        with self.engine.begin() as connection:
            self._set_utc(connection)
            for station in stations:
                statement = (
                    "INSERT INTO stations (station_id, payload) VALUES (:id, :payload) "
                    "ON DUPLICATE KEY UPDATE payload = VALUES(payload)"
                    if self.engine.dialect.name == "mysql"
                    else "INSERT INTO stations (station_id, payload) VALUES (:id, :payload) "
                    "ON CONFLICT(station_id) DO UPDATE SET payload = excluded.payload"
                )
                connection.execute(
                    text(statement),
                    {
                        "id": station["station_id"],
                        "payload": json.dumps(station, ensure_ascii=True),
                    },
                )
        return len(stations)

    def ingest(
        self,
        raw_payload: bytes,
        *,
        source: str,
        topic: str | None = None,
        source_path: str | None = None,
        line_number: int | None = None,
        connection: Connection | None = None,
    ) -> str:
        """Validate and durably store one payload, returning its disposition."""
        try:
            raw_text = raw_payload.decode("utf-8")
            event = parse_json_record(raw_text)
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            issue = Issue("error", "json", str(exc))
            self._quarantine(
                raw_payload, source, topic, [issue], source_path, line_number, connection
            )
            return "rejected"

        issues = validate_event(event, self.station_ids)
        if any(issue.severity == "error" for issue in issues):
            self._quarantine(
                raw_payload, source, topic, issues, source_path, line_number, connection
            )
            return "rejected"

        timestamp = utc_from_source_time(parse_source_timestamp(event["ts"]))
        return self._persist_event(
            event, raw_text, timestamp, issues, line_number, connection
        )

    def quarantine_payload(
        self,
        raw_payload: bytes,
        *,
        source: str,
        topic: str,
        issues: list[Issue],
    ) -> None:
        """Durably quarantine a syntactically valid payload that violates routing rules."""
        self._quarantine(raw_payload, source, topic, issues, None, None, None)

    def _persist_event(
        self,
        event: dict[str, Any],
        raw_text: str,
        timestamp: datetime,
        issues: list[Issue],
        line_number: int | None,
        connection: Connection | None,
    ) -> str:
        """Insert once; preserve first payload and audit conflicting sequences."""
        seq = event["seq"]
        payload_digest = content_hash(event)
        issue_json = json.dumps([asdict(issue) for issue in issues], ensure_ascii=True) if issues else None
        status = "warning" if issues else "valid"
        if self.engine.dialect.name == "mysql":
            insert = (
                "INSERT INTO events "
                "(seq, type, ts_utc, payload, validation_status, validation_reason, source_line_number) "
                "VALUES (:seq, :type, :ts, :payload, :status, :reason, :line) "
                "ON DUPLICATE KEY UPDATE seq = seq"
            )
        else:
            insert = (
                "INSERT INTO events "
                "(seq, type, ts_utc, payload, validation_status, validation_reason, source_line_number) "
                "VALUES (:seq, :type, :ts, :payload, :status, :reason, :line) "
                "ON CONFLICT(seq) DO NOTHING"
            )

        transaction = self.engine.begin() if connection is None else nullcontext(connection)
        with transaction as active_connection:
            if connection is None:
                self._set_utc(active_connection)
            existing = active_connection.execute(
                text("SELECT payload FROM events WHERE seq = :seq"),
                {"seq": seq},
            ).scalar_one_or_none()
            if existing is not None:
                return self._existing_disposition(
                    active_connection,
                    seq,
                    payload_digest,
                    existing,
                    raw_text,
                )
            result = active_connection.execute(
                text(insert),
                {
                    "seq": seq,
                    "type": event["type"],
                    "ts": timestamp,
                    "payload": raw_text,
                    "status": status,
                    "reason": issue_json,
                    "line": line_number,
                },
            )
            if result.rowcount == 1:
                return "warning" if issues else "stored"
            existing = active_connection.execute(
                text("SELECT payload FROM events WHERE seq = :seq"),
                {"seq": seq},
            ).scalar_one_or_none()
            if existing is None:
                raise RuntimeError(f"event insert failed without an existing sequence: {seq}")
            return self._existing_disposition(
                active_connection,
                seq,
                payload_digest,
                existing,
                raw_text,
            )
        return "duplicate"

    def _existing_disposition(
        self,
        connection: Connection,
        seq: int,
        payload_digest: str,
        existing: str,
        new_payload: str,
    ) -> str:
        try:
            existing_event = parse_json_record(existing)
            existing_digest = content_hash(existing_event)
        except (TypeError, ValueError, RecursionError):
            existing_digest = hashlib.sha256(existing.encode("utf-8")).hexdigest()
        if existing_digest != payload_digest:
            self._record_conflict(
                connection, seq, existing_digest, payload_digest, existing, new_payload
            )
            return "conflict"
        return "duplicate"

    def _record_conflict(
        self,
        connection: Connection,
        seq: int,
        old_hash: str,
        new_hash: str,
        old_payload: str,
        new_payload: str,
    ) -> None:
        """Record a changed payload once while keeping the original event intact."""
        statement = (
            "INSERT IGNORE INTO event_conflicts "
            "(seq, old_hash, new_hash, old_payload, new_payload) "
            "VALUES (:seq, :old_hash, :new_hash, :old_payload, :new_payload)"
            if self.engine.dialect.name == "mysql"
            else "INSERT OR IGNORE INTO event_conflicts "
            "(seq, old_hash, new_hash, old_payload, new_payload) "
            "VALUES (:seq, :old_hash, :new_hash, :old_payload, :new_payload)"
        )
        connection.execute(
            text(statement),
            {
                "seq": seq,
                "old_hash": old_hash,
                "new_hash": new_hash,
                "old_payload": old_payload,
                "new_payload": new_payload,
            },
        )

    def _quarantine(
        self,
        raw_payload: bytes,
        source: str,
        topic: str | None,
        issues: list[Issue],
        source_path: str | None,
        line_number: int | None,
        connection: Connection | None,
    ) -> None:
        """Persist a rejected source line or MQTT payload with stable identity."""
        serialized_issues = json.dumps([asdict(issue) for issue in issues], ensure_ascii=True)
        raw_text = raw_payload.decode("utf-8", errors="replace")
        transaction = self.engine.begin() if connection is None else nullcontext(connection)
        with transaction as active_connection:
            if connection is None:
                self._set_utc(active_connection)
            if source_path is not None and line_number is not None:
                statement = (
                    "INSERT INTO rejected_lines (source_path, line_number, raw_text, issues) "
                    "VALUES (:source, :line, :payload, :issues) "
                    "ON DUPLICATE KEY UPDATE issues = VALUES(issues)"
                    if self.engine.dialect.name == "mysql"
                    else "INSERT INTO rejected_lines (source_path, line_number, raw_text, issues) "
                    "VALUES (:source, :line, :payload, :issues) "
                    "ON CONFLICT(source_path, line_number) DO UPDATE SET issues = excluded.issues"
                )
                params = {
                    "source": source_path,
                    "line": line_number,
                    "payload": raw_text,
                    "issues": serialized_issues,
                }
            else:
                payload_hash = hashlib.sha256(raw_payload).hexdigest()
                statement = (
                    "INSERT IGNORE INTO rejected_messages "
                    "(source, topic, payload_hash, raw_payload_base64, issues) "
                    "VALUES (:source, :topic, :digest, :payload, :issues)"
                    if self.engine.dialect.name == "mysql"
                    else "INSERT OR IGNORE INTO rejected_messages "
                    "(source, topic, payload_hash, raw_payload_base64, issues) "
                    "VALUES (:source, :topic, :digest, :payload, :issues)"
                )
                params = {
                    "source": source,
                    "topic": topic or "",
                    "digest": payload_hash,
                    "payload": base64.b64encode(raw_payload).decode("ascii"),
                    "issues": serialized_issues,
                }
            active_connection.execute(text(statement), params)

    def _set_utc(self, connection: Connection) -> None:
        if self.engine.dialect.name == "mysql":
            connection.execute(text("SET SESSION time_zone='+00:00'"))
