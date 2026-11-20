import json
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from processor.validation import load_station_ids, parse_json_record, parse_source_timestamp, validate_event


def trip() -> dict:
    return {
        "type": "trip_ended", "ts": "2024-03-20T00:02:39-04:00", "seq": 53725,
        "ride_id": "ride", "rideable_type": "electric_bike", "member_casual": "casual",
        "started_at": "2024-03-19T23:59:24-04:00", "ended_at": "2024-03-20T00:02:39-04:00",
        "duration_s": 195, "start_station_id": "HB603", "end_station_id": "HB201",
        "start_lat": 40.746, "start_lng": -74.028, "end_lat": 40.751, "end_lng": -74.024,
        "extra": {"preserved": True},
    }


class ValidationTests(unittest.TestCase):
    def test_timezone_is_preserved_and_naive_or_wrong_offset_rejected(self):
        timestamp = parse_source_timestamp("2024-03-19T23:59:24-04:00")
        self.assertEqual(timestamp.utcoffset(), timedelta(hours=-4))
        self.assertEqual(timestamp.hour, 23)
        for value in ("2024-03-19T23:59:24", "2024-03-19T23:59:24Z",
                      "2024-03-19T23:59:24-05:00", "2024-02-30T00:00:00-04:00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_source_timestamp(value)

    def test_json_requires_object_and_standard_numbers(self):
        for line in ('{', '[]', '{"x": NaN}'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                parse_json_record(line)

    def test_trip_preserves_unknown_fields_and_warns_about_missing_end(self):
        event = trip()
        original = json.loads(json.dumps(event))
        self.assertEqual(validate_event(event, {"HB603", "HB201"}), [])
        self.assertEqual(event, original)
        event["end_station_id"] = None
        event["end_lat"] = None
        issues = validate_event(event, {"HB603", "HB201"})
        self.assertEqual({issue.field for issue in issues}, {"end_station_id", "end_lat"})
        self.assertTrue(all(issue.severity == "warning" for issue in issues))

    def test_unknown_stations_are_warnings_and_invalid_values_are_errors(self):
        event = trip()
        event.update({"start_station_id": "outside", "duration_s": -1, "start_lat": True,
                      "member_casual": "other", "ts": "bad"})
        issues = validate_event(event, {"HB201"})
        self.assertIn(("warning", "start_station_id"), {(i.severity, i.field) for i in issues})
        self.assertEqual({i.field for i in issues if i.severity == "error"},
                         {"duration_s", "start_lat", "member_casual", "ts"})

    def test_missing_and_out_of_range_start_coordinates(self):
        event = trip()
        event["start_lat"] = None
        event["start_lng"] = 10 ** 400
        issues = validate_event(event, {"HB603", "HB201"})
        self.assertIn(("warning", "start_lat"), {(i.severity, i.field) for i in issues})
        self.assertIn(("error", "start_lng"), {(i.severity, i.field) for i in issues})

    def test_status_and_unknown_event_validation(self):
        event = {
            "type": "station_status", "ts": "2024-03-13T00:07:33-04:00", "seq": 1,
            "station_id": "JC075", "num_bikes_available": 1, "num_ebikes_available": 2,
            "num_bikes_disabled": 0, "num_docks_available": 0, "num_docks_disabled": 0,
            "is_installed": 1, "is_renting": 1, "is_returning": 1,
        }
        issues = validate_event(event, {"JC075"})
        self.assertEqual([(i.severity, i.field) for i in issues],
                         [("warning", "num_ebikes_available")])
        event["type"] = "unexpected"
        self.assertIn("type", {i.field for i in validate_event(event, {"JC075"})})

    def test_station_validation_rejects_duplicate_ids(self):
        station = {"station_id": "JC075", "station_uuid": "id", "name": "Station",
                   "city": "Jersey City", "lat": 40.0, "lon": -74.0, "capacity": 10}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stations.json"
            path.write_text(json.dumps([station, station]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate station_id"):
                load_station_ids(path)

    def test_cli_reports_raw_bad_records_and_fails(self):
        station = {"station_id": "HB603", "station_uuid": "id", "name": "Station",
                   "city": "Hoboken", "lat": 40.0, "lon": -74.0, "capacity": 10}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "stations.json").write_text(json.dumps([station]), encoding="utf-8")
            (path / "events.jsonl").write_text('not json\n', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "processor.inspect_dataset", "--stations",
                 str(path / "stations.json"), str(path / "events.jsonl")],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["raw"], "not json")
        self.assertEqual(json.loads(result.stderr)["records_with_errors"], 1)

    def test_cli_warnings_do_not_fail_and_keep_original_line(self):
        station = {"station_id": "HB603", "station_uuid": "id", "name": "Station",
                   "city": "Hoboken", "lat": 40.0, "lon": -74.0, "capacity": 10}
        event = trip()
        event["end_station_id"] = None
        raw = json.dumps(event)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "stations.json").write_text(json.dumps([station]), encoding="utf-8")
            (path / "events.jsonl").write_text(raw + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "processor.inspect_dataset", "--stations",
                 str(path / "stations.json"), str(path / "events.jsonl")],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["raw"], raw)
        self.assertEqual(json.loads(result.stderr)["records_with_warnings"], 1)


if __name__ == "__main__":
    unittest.main()
