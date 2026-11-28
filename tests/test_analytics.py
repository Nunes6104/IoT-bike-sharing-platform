"""Historical aggregation tests using an isolated SQLite database."""

import json
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from processor.analytics import AnalyticsService, parse_local_range
from processor.dataset import STAGE2_SEQUENCE_START


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE events (
                    seq INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    ts_utc DATETIME NOT NULL,
                    payload TEXT NOT NULL,
                    validation_status TEXT NOT NULL
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
                    validation_status TEXT NOT NULL
                )
            """))
            station = {
                "station_id": "JC115", "name": "Test Station", "capacity": 20,
                "station_uuid": "test", "lat": 40.7, "lon": -74.0, "city": "Jersey City",
            }
            connection.execute(
                text("INSERT INTO stations VALUES (:id, :payload)"),
                {"id": station["station_id"], "payload": json.dumps(station)},
            )
            self._insert_event(connection, 1, self._trip("ride-1", "2024-03-20T05:59:30-04:00"))
            self._insert_event(connection, 2, self._trip("ride-2", "2024-03-20T06:00:00-04:00"))
            self._insert_event(connection, 3, self._trip("ride-1", "2024-03-20T05:59:30-04:00"))
            self._insert_event(connection, 4, {
                "type": "station_status",
                "ts": "2024-03-20T06:00:00-04:00",
                "station_id": "JC115",
                "num_bikes_available": 0,
                "num_docks_available": 20,
            })

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _trip(ride_id, started_at):
        return {
            "type": "trip_ended",
            "ts": started_at,
            "started_at": started_at,
            "ended_at": started_at,
            "duration_s": 3600,
            "ride_id": ride_id,
            "rideable_type": "electric_bike",
            "member_casual": "member",
            "start_station_id": "JC115",
            "end_station_id": "JC115",
            "start_lat": 40.7,
            "start_lng": -74.0,
            "end_lat": 40.71,
            "end_lng": -74.0,
        }

    @staticmethod
    def _insert_event(connection, seq, event, table="events"):
        event["seq"] = seq
        timestamp_utc = datetime.fromisoformat(event["ts"]).astimezone(timezone.utc)
        connection.execute(
            text(
                f"INSERT INTO {table} "
                "(seq, type, ts_utc, payload, validation_status) "
                "VALUES (:seq, :type, :ts, :payload, 'valid')"
            ),
            {
                "seq": seq,
                "type": event["type"],
                "ts": timestamp_utc.replace(tzinfo=None),
                "payload": json.dumps(event),
            },
        )

    def test_summary_deduplicates_rides_and_uses_half_open_local_ranges(self):
        result = AnalyticsService(self.engine).summarize(
            "2024-03-20T00:00:00-04:00",
            "2024-03-20T06:00:00-04:00",
            "hour",
        )
        self.assertEqual(result["summary"]["completed_trips"], 1)
        self.assertEqual(result["summary"]["duplicate_ride_records"], 1)
        self.assertEqual(result["time_of_day"][0], {"period": "night", "trips": 1})
        self.assertEqual(result["trends"][-1]["trips"], 1)
        self.assertEqual(result["station_utilization"][0]["departures_member"], 1)

    def test_status_updates_at_end_boundary_are_excluded(self):
        result = AnalyticsService(self.engine).summarize(
            "2024-03-20T00:00:00-04:00",
            "2024-03-20T06:00:00-04:00",
            "day",
        )
        self.assertEqual(result["station_utilization"][0]["observed_status_updates"], 0)
        self.assertIsNone(result["station_utilization"][0]["empty_update_share"])

    def test_analytics_uses_live_stage2_and_ignores_archived_stage2_rows(self):
        with self.engine.begin() as connection:
            self._insert_event(
                connection,
                STAGE2_SEQUENCE_START,
                self._trip("archived-stage2", "2024-03-20T08:00:00-04:00"),
            )
            self._insert_event(
                connection,
                STAGE2_SEQUENCE_START + 1,
                self._trip("live-stage2", "2024-03-20T09:00:00-04:00"),
                table="online_events",
            )

        result = AnalyticsService(self.engine).summarize(
            "2024-03-20T00:00:00-04:00",
            "2024-03-21T00:00:00-04:00",
        )

        self.assertEqual(result["summary"]["completed_trips"], 3)
        self.assertEqual(
            sum(point["trips"] for point in result["trends"]),
            3,
        )

    def test_range_requires_source_offset_and_is_bounded(self):
        with self.assertRaises(ValueError):
            parse_local_range("2024-03-20T00:00:00", "2024-03-20T01:00:00")
        with self.assertRaises(ValueError):
            parse_local_range("2024-03-01T00:00:00-04:00", "2024-04-15T00:00:00-04:00")


if __name__ == "__main__":
    unittest.main()
