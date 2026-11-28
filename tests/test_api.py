"""HTTPS API handler authorization and request validation tests."""

import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from processor.api import create_handler


class AnalyticsApiTests(unittest.TestCase):
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
            connection.execute(text("""
                CREATE TABLE ml_models (
                    model_id TEXT PRIMARY KEY, training_start TEXT, training_end TEXT,
                    algorithm TEXT, cluster_count INTEGER, feature_names TEXT,
                    metrics TEXT, active INTEGER, created_at TEXT
                )
            """))
            connection.execute(text("""
                CREATE TABLE ml_profiles (
                    model_id TEXT, station_id TEXT, window_start TEXT, window_end TEXT,
                    city TEXT, capacity INTEGER, cluster_id INTEGER,
                    features TEXT, flags TEXT
                )
            """))
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(self.engine, "test-token")
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.engine.dispose()

    def request(self, path, token=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        status = response.status
        connection.close()
        return status, payload

    def test_api_requires_bearer_authentication(self):
        status, payload = self.request("/api/analytics")
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "unauthorized"})

    def test_invalid_ranges_are_rejected_after_authentication(self):
        status, payload = self.request(
            "/api/analytics?start=bad&end=bad", "test-token"
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_valid_summary_is_json_and_scoped(self):
        status, payload = self.request(
            "/api/analytics?start=2024-03-20T00%3A00%3A00-04%3A00"
            "&end=2024-03-21T00%3A00%3A00-04%3A00&bucket=day",
            "test-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["completed_trips"], 0)
        self.assertEqual(payload["bucket"], "day")

    def test_latest_station_snapshot_requires_authentication_and_rejects_query(self):
        status, payload = self.request("/api/stations/latest")
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "unauthorized"})

        status, payload = self.request("/api/stations/latest?station_id=JC001", "test-token")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_latest_station_snapshot_returns_empty_reference_list(self):
        status, payload = self.request("/api/stations/latest", "test-token")
        self.assertEqual(status, 200)
        self.assertEqual(payload["stations"], [])
        self.assertEqual(payload["active_trips"], [])
        self.assertIn("fetched_at", payload)
        self.assertIsNone(payload["latest_committed_event_at"])

    def test_ml_model_and_profiles_require_authentication(self):
        status, payload = self.request("/api/ml/model")
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "unauthorized"})

        status, payload = self.request(
            "/api/ml/profiles?start=2024-03-20&end=2024-03-21", "test-token"
        )
        self.assertEqual(status, 200)
        self.assertIsNone(payload["model"])
        self.assertEqual(payload["profiles"], [])

    def test_ml_profile_range_is_bounded_and_end_is_exclusive(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO ml_models VALUES "
                    "('model-1', '2024-03-13', '2024-03-20', 'kmeans', 2, '[]', '{}', 1, 'now')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO ml_profiles VALUES "
                    "(:model, :station, :start, :end, :city, :capacity, :cluster, "
                    ":features, :flags)"
                ),
                {
                    "model": "model-1",
                    "station": "JC115",
                    "start": "2024-03-20",
                    "end": "2024-03-21",
                    "city": "Jersey City",
                    "capacity": 20,
                    "cluster": 1,
                    "features": '{"trips_per_capacity":0.1}',
                    "flags": '[{"type":"underused_relative","observed":0.1}]',
                },
            )
            connection.execute(
                text(
                    "INSERT INTO ml_profiles VALUES "
                    "('model-1', 'HB101', '2024-03-21', '2024-03-22', "
                    "'Hoboken', 20, 0, '{}', '[]')"
                )
            )
        status, payload = self.request(
            "/api/ml/profiles?start=2024-03-20&end=2024-03-21", "test-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual([row["station_id"] for row in payload["profiles"]], ["JC115"])
        self.assertEqual(payload["evolution"], [
            {"window_start": "2024-03-20", "cluster_id": 1, "station_count": 1}
        ])
        self.assertEqual(payload["flags"][0]["type"], "underused_relative")

        status, payload = self.request(
            "/api/ml/profiles?start=2024-03-20&end=2024-05-01", "test-token"
        )
        self.assertEqual(status, 400)
        self.assertIn("31 days", payload["error"])

    def test_ml_flags_endpoint_returns_only_explainable_flags(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO ml_models VALUES "
                    "('model-1', '2024-03-13', '2024-03-20', 'kmeans', 2, '[]', '{}', 1, 'now')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO ml_profiles VALUES "
                    "('model-1', 'JC115', '2024-03-20', '2024-03-21', "
                    "'Jersey City', 20, 1, '{}', '[{\"type\":\"frequently_empty\"}]')"
                )
            )
        status, payload = self.request(
            "/api/ml/flags?start=2024-03-20&end=2024-03-21", "test-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["flags"]), 1)
        self.assertEqual(payload["flags"][0]["station_id"], "JC115")


if __name__ == "__main__":
    unittest.main()
