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
        self.assertIn("fetched_at", payload)
        self.assertIsNone(payload["latest_committed_event_at"])


if __name__ == "__main__":
    unittest.main()
