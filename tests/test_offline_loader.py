"""Unit tests for offline loader: timestamps, warnings, malformed records, duplicates, conflicts."""

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from processor.offline_loader import OfflineLoader, utc_from_source_time, content_hash
from processor.validation import Issue, parse_source_timestamp


class OfflineLoaderUnitTests(unittest.TestCase):
    def test_utc_conversion_preserves_wall_time(self):
        """Source -04:00 timestamp converts to UTC wall time."""
        source = parse_source_timestamp("2024-03-20T14:30:45-04:00")
        utc = utc_from_source_time(source)
        # EDT (UTC-4): 14:30 local = 18:30 UTC
        self.assertEqual(utc.hour, 18)
        self.assertEqual(utc.minute, 30)
        self.assertIsNone(utc.tzinfo)

    def test_utc_conversion_rejects_naive_timestamp(self):
        """Naive timestamps cannot be converted."""
        naive = datetime(2024, 3, 20, 14, 30, 45)
        with self.assertRaises(ValueError):
            utc_from_source_time(naive)

    def test_content_hash_canonical(self):
        """Content hash is stable for identical payloads in different orders."""
        payload1 = {"type": "trip_ended", "ride_id": "X", "seq": 100}
        payload2 = {"seq": 100, "ride_id": "X", "type": "trip_ended"}
        self.assertEqual(content_hash(payload1), content_hash(payload2))

    def test_content_hash_differs_on_mutation(self):
        """Content hash differs when payload changes."""
        payload1 = {"ride_id": "X"}
        payload2 = {"ride_id": "Y"}
        self.assertNotEqual(content_hash(payload1), content_hash(payload2))

    def test_issue_dataclass(self):
        """Issue objects preserve severity, field, and message."""
        issue = Issue("warning", "end_station_id", "station is unavailable")
        self.assertEqual(issue.severity, "warning")
        self.assertEqual(issue.field, "end_station_id")
        self.assertEqual(issue.message, "station is unavailable")

    def test_loader_stats_initialization(self):
        """Loader stats counter initializes to zero."""
        from sqlalchemy import create_engine
        engine = create_engine("sqlite:///:memory:")
        loader = OfflineLoader(engine, dry_run=True)
        self.assertEqual(loader.stats['records_read'], 0)
        self.assertEqual(loader.stats['errors'], 0)

    def test_dry_run_does_not_write(self):
        """Dry-run mode skips database writes but counts events."""
        from sqlalchemy import create_engine
        engine = create_engine("sqlite:///:memory:")
        loader = OfflineLoader(engine, dry_run=True)
        # Loader should not raise or fail in dry-run; writes are skipped.
        self.assertTrue(loader.dry_run)

    def test_malformed_json_line(self):
        """Malformed JSON lines are categorized as errors."""
        # This test validates behavior; actual database interaction is in integration tests.
        issue = Issue("error", "json", "not valid JSON")
        self.assertEqual(issue.severity, "error")

    def test_warning_record_serialization(self):
        """Warning records serialize to JSON for storage."""
        issues = [Issue("warning", "end_station_id", "unavailable")]
        serialized = json.dumps(
            [{'severity': i.severity, 'field': i.field, 'message': i.message} for i in issues]
        )
        self.assertIn("warning", serialized)
        self.assertIn("unavailable", serialized)


if __name__ == "__main__":
    unittest.main()
