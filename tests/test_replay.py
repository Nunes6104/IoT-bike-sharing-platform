"""Replay routing, timing, checkpoint, and resume tests."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from processor.subscriber import validate_topic_event
from publisher.replay import event_topic, replay_file


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        station = [{
            "station_id": "JC115",
            "station_uuid": "test",
            "name": "Test Station",
            "city": "Jersey City",
            "lat": 40.7,
            "lon": -74.0,
            "capacity": 20,
        }]
        self.stations = self.root / "stations.json"
        self.stations.write_text(json.dumps(station), encoding="utf-8")
        self.data = self.root / "events.jsonl"
        self.checkpoint = self.root / "checkpoint.json"
        self.events = [
            self._event(1, "2024-03-20T00:00:00-04:00"),
            self._event(2, "2024-03-20T00:01:00-04:00"),
        ]
        self.data.write_text(
            "".join(json.dumps(event) + "\n" for event in self.events),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _event(seq, timestamp):
        return {
            "type": "station_status",
            "ts": timestamp,
            "station_id": "JC115",
            "num_bikes_available": 4,
            "num_ebikes_available": 2,
            "num_bikes_disabled": 0,
            "num_docks_available": 10,
            "num_docks_disabled": 0,
            "is_installed": 1,
            "is_renting": 1,
            "is_returning": 1,
            "seq": seq,
        }

    def test_routes_status_and_validates_topic_payload_agreement(self):
        event = self.events[0]
        topic = event_topic(event, "10")
        self.assertEqual(topic, "idc/fc10/status/JC115")
        self.assertEqual(validate_topic_event(topic, "10", event), [])
        self.assertTrue(validate_topic_event("idc/fc11/status/JC115", "10", event))
        self.assertTrue(validate_topic_event("idc/fc10/status/HB101", "10", event))

    def test_replay_preserves_scaled_interval_and_checkpoints_acknowledgments(self):
        delays = []
        published = []
        count = replay_file(
            self.data,
            self.stations,
            "10",
            60,
            self.checkpoint,
            lambda topic, payload: published.append((topic, payload)),
            sleep=delays.append,
            clock=lambda: 0.0,
        )
        self.assertEqual(count, 2)
        self.assertEqual(delays, [1.0])
        self.assertEqual(json.loads(self.checkpoint.read_text())["next_line"], 3)
        self.assertEqual(len(published), 2)

    def test_failure_does_not_checkpoint_unacknowledged_record_and_resume(self):
        attempts = []

        def fail_second(topic, payload):
            attempts.append(payload)
            if len(attempts) == 2:
                raise ConnectionError("simulated lost broker acknowledgment")

        with self.assertRaises(ConnectionError):
            replay_file(
                self.data, self.stations, "10", 1, self.checkpoint, fail_second,
                sleep=lambda delay: None, clock=lambda: 0.0,
            )
        saved = json.loads(self.checkpoint.read_text(encoding="utf-8")) \
            if self.checkpoint.exists() else {"next_line": 1}
        self.assertEqual(saved["next_line"], 1)
        resumed = []
        replay_file(
            self.data, self.stations, "10", 1, self.checkpoint,
            lambda topic, payload: resumed.append(payload),
            sleep=lambda delay: None, clock=lambda: 0.0,
        )
        self.assertEqual(resumed, [json.dumps(event).encode() for event in self.events])

    def test_batch_checkpoint_excludes_unacknowledged_event(self):
        events = [
            self._event(
                index + 1,
                (datetime.fromisoformat("2024-03-20T00:00:00-04:00")
                 + timedelta(seconds=index)).isoformat(),
            )
            for index in range(101)
        ]
        data = self.root / "batch.jsonl"
        data.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        attempts = 0

        def fail_last(topic, payload):
            nonlocal attempts
            attempts += 1
            if attempts == 101:
                raise ConnectionError("simulated lost broker acknowledgment")

        with self.assertRaises(ConnectionError):
            replay_file(
                data, self.stations, "10", 1, self.checkpoint, fail_last,
                sleep=lambda delay: None, clock=lambda: 0.0,
            )
        saved = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(saved["next_line"], 101)

    def test_failed_qos_ack_leaves_batch_uncheckpointed(self):
        class PublishReceipt:
            def __init__(self, fail=False):
                self.fail = fail

            def wait_for_publish(self, timeout):
                if self.fail:
                    raise TimeoutError("simulated QoS acknowledgment timeout")

            def is_published(self):
                return not self.fail

        calls = 0

        def publish(topic, payload):
            nonlocal calls
            calls += 1
            return PublishReceipt(fail=calls == 2)

        with self.assertRaises(TimeoutError):
            replay_file(
                self.data, self.stations, "10", 1, self.checkpoint, publish,
                sleep=lambda delay: None, clock=lambda: 0.0,
            )
        self.assertFalse(self.checkpoint.exists())

    def test_resume_rejects_changed_dataset_or_speed(self):
        replay_file(
            self.data, self.stations, "10", 1, self.checkpoint,
            lambda topic, payload: None,
            sleep=lambda delay: None, clock=lambda: 0.0,
        )
        with self.assertRaises(ValueError):
            replay_file(
                self.data, self.stations, "10", 2, self.checkpoint,
                lambda topic, payload: None,
            )

    def test_negative_speed_is_rejected(self):
        with self.assertRaises(ValueError):
            replay_file(
                self.data, self.stations, "10", 0, self.checkpoint,
                lambda topic, payload: None,
            )


if __name__ == "__main__":
    unittest.main()
