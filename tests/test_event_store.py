"""Persistence tests for idempotent and quarantined event ingestion."""

import base64
import json
import unittest
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from processor.dataset import STAGE2_SEQUENCE_START
from processor.event_store import EventStore


class EventStoreTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE events (
                    seq INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    ts_utc DATETIME NOT NULL,
                    payload TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    validation_reason TEXT,
                    source_line_number INTEGER
                )
            """))
            connection.execute(text("""
                CREATE TABLE online_events (
                    seq INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    ts_utc DATETIME NOT NULL,
                    payload TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    validation_reason TEXT,
                    source_line_number INTEGER
                )
            """))
            connection.execute(text("""
                CREATE TABLE event_conflicts (
                    seq INTEGER NOT NULL,
                    old_hash TEXT,
                    new_hash TEXT NOT NULL,
                    old_payload TEXT,
                    new_payload TEXT,
                    UNIQUE(seq, new_hash)
                )
            """))
            connection.execute(text("""
                CREATE TABLE rejected_lines (
                    source_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    issues TEXT NOT NULL,
                    PRIMARY KEY(source_path, line_number)
                )
            """))
            connection.execute(text("""
                CREATE TABLE rejected_messages (
                    source TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    raw_payload_base64 TEXT NOT NULL,
                    issues TEXT NOT NULL,
                    PRIMARY KEY(source, topic, payload_hash)
                )
            """))
        self.store = EventStore(self.engine, {"JC115"})

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def event(sequence=STAGE2_SEQUENCE_START, station_id="JC115"):
        return {
            "type": "station_status",
            "ts": "2024-03-20T14:30:00-04:00",
            "station_id": station_id,
            "num_bikes_available": 4,
            "num_ebikes_available": 2,
            "num_bikes_disabled": 0,
            "num_docks_available": 10,
            "num_docks_disabled": 0,
            "is_installed": 1,
            "is_renting": 1,
            "is_returning": 1,
            "seq": sequence,
        }

    def test_identical_delivery_is_a_noop(self):
        payload = json.dumps(self.event()).encode()
        self.assertEqual(self.store.ingest(payload, source="mqtt", topic="idc/fc10/status/JC115"), "stored")
        self.assertEqual(self.store.ingest(payload, source="mqtt", topic="idc/fc10/status/JC115"), "duplicate")
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(text("SELECT COUNT(*) FROM online_events")).scalar_one(),
                1,
            )

    def test_mysql_duplicate_detection_does_not_depend_on_rowcount(self):
        payload = json.dumps(self.event(), separators=(",", ":"))

        class ExistingPayload:
            def scalar_one_or_none(self):
                return payload

        class ExistingEventConnection:
            def __init__(self):
                self.statements = []

            def execute(self, statement, parameters):
                self.statements.append(str(statement))
                return ExistingPayload()

        connection = ExistingEventConnection()
        mysql_engine = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
        store = EventStore(mysql_engine, {"JC115"})
        disposition = store._persist_event(
            self.event(),
            payload,
            datetime(2024, 3, 20, 18, 30),
            [],
            None,
            connection,
        )
        self.assertEqual(disposition, "duplicate")
        self.assertEqual(len(connection.statements), 1)

    def test_mysql_insert_race_still_audits_conflicting_payload(self):
        original = json.dumps(self.event(), separators=(",", ":"))
        changed_event = self.event(station_id="JC116")
        changed = json.dumps(changed_event, separators=(",", ":"))

        class FakeResult:
            def __init__(self, rowcount=None, payload=None):
                self.rowcount = rowcount
                self.payload = payload

            def scalar_one_or_none(self):
                return self.payload

        class RacingConnection:
            def __init__(self):
                self.results = [
                    FakeResult(payload=None),
                    FakeResult(rowcount=0),
                    FakeResult(payload=original),
                    FakeResult(),
                ]

            def execute(self, statement, parameters):
                return self.results.pop(0)

        connection = RacingConnection()
        mysql_engine = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
        store = EventStore(mysql_engine, {"JC115"})
        disposition = store._persist_event(
            changed_event,
            changed,
            datetime(2024, 3, 20, 18, 30),
            [],
            None,
            connection,
        )
        self.assertEqual(disposition, "conflict")
        self.assertEqual(connection.results, [])

    def test_conflicting_sequence_preserves_first_event_and_audits_once(self):
        original = json.dumps(self.event()).encode()
        changed = json.dumps(self.event(station_id="JC116")).encode()
        self.assertEqual(self.store.ingest(original, source="mqtt"), "stored")
        self.assertEqual(self.store.ingest(changed, source="mqtt"), "conflict")
        self.assertEqual(self.store.ingest(changed, source="mqtt"), "conflict")
        with self.engine.connect() as connection:
            payload = connection.execute(
                text("SELECT payload FROM online_events WHERE seq=:seq"),
                {"seq": STAGE2_SEQUENCE_START},
            ).scalar_one()
            conflicts = connection.execute(text("SELECT COUNT(*) FROM event_conflicts")).scalar_one()
        self.assertEqual(json.loads(payload)["station_id"], "JC115")
        self.assertEqual(conflicts, 1)

    def test_invalid_mqtt_payload_is_quarantined_idempotently(self):
        payload = b"\xffnot-json"
        for _ in range(2):
            self.assertEqual(
                self.store.ingest(payload, source="mqtt", topic="idc/fc10/status/JC115"),
                "rejected",
            )
        with self.engine.connect() as connection:
            row = connection.execute(
                text("SELECT raw_payload_base64 FROM rejected_messages")
            ).scalar_one()
        self.assertEqual(base64.b64decode(row), payload)

    def test_warning_event_is_persisted_with_source_timestamp_converted(self):
        event = self.event(station_id="OUTSIDE")
        disposition = self.store.ingest(json.dumps(event).encode(), source="mqtt")
        self.assertEqual(disposition, "warning")
        with self.engine.connect() as connection:
            status, timestamp = connection.execute(
                text("SELECT validation_status, ts_utc FROM online_events WHERE seq=:seq"),
                {"seq": STAGE2_SEQUENCE_START},
            ).one()
        self.assertEqual(status, "warning")
        self.assertIn("18:30:00", str(timestamp))

    def test_stage_routing_keeps_offline_events_immutable(self):
        offline = self.event(sequence=1)
        offline_payload = json.dumps(offline).encode()
        self.assertEqual(self.store.ingest(offline_payload, source="offline"), "stored")

        mqtt_stage1 = {**offline, "num_bikes_available": 8}
        self.assertEqual(
            self.store.ingest(json.dumps(mqtt_stage1).encode(), source="mqtt"),
            "rejected",
        )
        offline_stage2 = self.event(sequence=STAGE2_SEQUENCE_START)
        self.assertEqual(
            self.store.ingest(
                json.dumps(offline_stage2).encode(), source="offline"
            ),
            "rejected",
        )

        with self.engine.connect() as connection:
            stored = connection.execute(
                text("SELECT payload FROM events WHERE seq=1")
            ).scalar_one()
            online_count = connection.execute(
                text("SELECT COUNT(*) FROM online_events")
            ).scalar_one()
            quarantined = connection.execute(
                text("SELECT COUNT(*) FROM rejected_messages")
            ).scalar_one()
        self.assertEqual(json.loads(stored), offline)
        self.assertEqual(online_count, 0)
        self.assertEqual(quarantined, 2)


if __name__ == "__main__":
    unittest.main()
