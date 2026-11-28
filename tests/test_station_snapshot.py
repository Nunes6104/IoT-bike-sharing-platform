"""Latest station snapshot ordering and unknown-data behavior."""

import json
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from processor.dataset import STAGE2_SEQUENCE_START
from processor.station_snapshot import StationSnapshotService


class StationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE events (
                    seq INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    ts_utc DATETIME NOT NULL,
                    payload TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    validation_reason TEXT
                )
            """))
            connection.execute(text("""
                CREATE TABLE stations (station_id TEXT PRIMARY KEY, payload TEXT NOT NULL)
            """))
            connection.execute(text("""
                CREATE TABLE online_events (
                    seq INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    ts_utc DATETIME NOT NULL,
                    payload TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    validation_reason TEXT
                )
            """))
            references = [
                {
                    "station_id": "JC001", "name": "Valid", "lat": 40.7,
                    "lon": -74.0, "capacity": 20, "city": "Jersey City",
                },
                {
                    "station_id": "JC002", "name": "No coordinates", "lat": None,
                    "lon": None, "capacity": 10, "city": "Jersey City",
                },
                {
                    "station_id": "JC003", "name": "No report", "lat": 40.71,
                    "lon": -74.01, "capacity": 12, "city": "Hoboken",
                },
            ]
            for station in references:
                connection.execute(
                    text("INSERT INTO stations (station_id, payload) VALUES (:id, :payload)"),
                    {"id": station["station_id"], "payload": json.dumps(station)},
                )

    def tearDown(self):
        self.engine.dispose()

    def insert_status(
        self, seq, source_time, bikes, *,
        validation="valid", reason=None, table=None,
    ):
        payload = {
            "type": "station_status",
            "station_id": "JC001",
            "ts": source_time,
            "num_bikes_available": bikes,
            "num_ebikes_available": min(bikes, 2),
            "num_bikes_disabled": 1,
            "num_docks_available": 4,
            "num_docks_disabled": 0,
            "is_installed": 1,
            "is_renting": 1,
            "is_returning": 1,
            "seq": seq,
        }
        with self.engine.begin() as connection:
            table = table or (
                "online_events" if seq >= STAGE2_SEQUENCE_START else "events"
            )
            connection.execute(
                text("""
                    INSERT INTO {table}
                        (seq, type, ts_utc, payload, validation_status, validation_reason)
                    VALUES (:seq, 'station_status', :ts, :payload, :validation, :reason)
                """.format(table=table)),
                {
                    "seq": seq,
                    "ts": datetime.fromisoformat(source_time).astimezone(timezone.utc).replace(tzinfo=None),
                    "payload": json.dumps(payload),
                    "validation": validation,
                    "reason": json.dumps(reason) if reason else None,
                },
            )

    def insert_trip_event(
        self, seq, event_type, ride_id, source_time, *,
        validation="valid", reason=None,
    ):
        payload = {
            "type": event_type,
            "seq": seq,
            "ts": source_time,
            "ride_id": ride_id,
            "start_station_id": "JC001",
            "rideable_type": "electric_bike",
            "member_casual": "member",
        }
        with self.engine.begin() as connection:
            table = "online_events" if seq >= STAGE2_SEQUENCE_START else "events"
            connection.execute(
                text("""
                    INSERT INTO {table}
                        (seq, type, ts_utc, payload, validation_status, validation_reason)
                    VALUES (:seq, :type, :ts, :payload, :validation, :reason)
                """.format(table=table)),
                {
                    "seq": seq,
                    "type": event_type,
                    "ts": datetime.fromisoformat(source_time).astimezone(timezone.utc).replace(tzinfo=None),
                    "payload": json.dumps(payload),
                    "validation": validation,
                    "reason": json.dumps(reason) if reason else None,
                },
            )

    def test_latest_report_uses_source_time_then_sequence_and_keeps_warnings(self):
        warning = [{"severity": "warning", "field": "num_bikes_available", "message": "unusual"}]
        self.insert_status(10, "2024-03-20T08:00:00-04:00", 3)
        self.insert_status(12, "2024-03-20T08:00:00-04:00", 5, validation="warning", reason=warning)
        self.insert_status(13, "2024-03-21T08:00:00-04:00", 1, validation="rejected")
        self.insert_status(15, "2024-03-19T23:59:59-04:00", 9)

        snapshot = StationSnapshotService(self.engine).latest()
        station = snapshot["stations"][0]
        self.assertEqual(station["status"]["seq"], 12)
        self.assertEqual(station["status"]["reported_at"], "2024-03-20T08:00:00-04:00")
        self.assertEqual(station["status"]["num_bikes_available"], 5)
        self.assertEqual(station["status"]["num_ebikes_available"], 2)
        self.assertEqual(station["status"]["warnings"], warning)
        self.assertEqual(snapshot["latest_committed_event_at"], "2024-03-20T12:00:00+00:00")

    def test_missing_status_and_coordinates_remain_explicit(self):
        snapshot = StationSnapshotService(self.engine).latest()
        unmappable = next(station for station in snapshot["stations"] if station["station_id"] == "JC002")
        unreported = next(station for station in snapshot["stations"] if station["station_id"] == "JC003")

        self.assertFalse(unmappable["mappable"])
        self.assertIsNone(unmappable["status"])
        self.assertTrue(unreported["mappable"])
        self.assertIsNone(unreported["status"])

    def test_out_of_order_insert_does_not_replace_newer_timestamp(self):
        self.insert_status(20, "2024-03-20T10:00:00-04:00", 8)
        self.insert_status(99, "2024-03-20T09:00:00-04:00", 1)

        snapshot = StationSnapshotService(self.engine).latest()
        self.assertEqual(snapshot["stations"][0]["status"]["seq"], 20)
        self.assertEqual(snapshot["stations"][0]["status"]["num_bikes_available"], 8)

    def test_active_trips_are_unmatched_stage2_starts_only(self):
        warning = [{"severity": "warning", "field": "start_station_id", "message": "unknown"}]
        self.insert_trip_event(20, "trip_started", "historical", "2024-03-19T23:59:00-04:00")
        self.insert_trip_event(53725, "trip_started", "closed", "2024-03-20T00:01:00-04:00")
        self.insert_trip_event(53726, "trip_ended", "closed", "2024-03-20T00:05:00-04:00")
        self.insert_trip_event(53727, "trip_started", "open", "2024-03-20T00:06:00-04:00")
        self.insert_trip_event(
            53728, "trip_ended", "open", "2024-03-20T00:07:00-04:00",
            validation="rejected",
        )
        self.insert_trip_event(
            53729, "trip_started", "warning", "2024-03-20T00:08:00-04:00",
            validation="warning", reason=warning,
        )

        snapshot = StationSnapshotService(self.engine).latest()

        self.assertEqual([trip["ride_id"] for trip in snapshot["active_trips"]], ["warning", "open"])
        self.assertEqual(snapshot["active_trips"][0]["started_at"], "2024-03-20T00:08:00-04:00")
        self.assertEqual(snapshot["active_trips"][0]["warnings"], warning)
        self.assertEqual(snapshot["active_trips"][1]["validation_status"], "valid")

    def test_snapshot_ignores_archived_stage2_rows_until_mqtt_replay(self):
        self.insert_status(
            73580, "2024-03-22T23:59:00-04:00", 0, table="events"
        )
        self.insert_status(
            STAGE2_SEQUENCE_START, "2024-03-20T00:01:00-04:00", 5
        )

        snapshot = StationSnapshotService(self.engine).latest()
        station = snapshot["stations"][0]

        self.assertEqual(station["status"]["seq"], STAGE2_SEQUENCE_START)
        self.assertEqual(station["status"]["num_bikes_available"], 5)
        self.assertEqual(
            snapshot["latest_committed_event_at"],
            "2024-03-20T04:01:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
