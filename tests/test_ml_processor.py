"""Focused tests for ML feature preparation, model selection, and operational flags."""

import json
import unittest
from datetime import date

from sqlalchemy import create_engine, text

from ml_processor.features import build_station_day_features
from ml_processor.modeling import MODEL_FORMAT_VERSION, predict_labels, train_model
from ml_processor.profiles import (
    _add_flags,
    _load_inputs,
    _model_format_is_current,
    _save_model,
    _save_profiles,
)
from ml_processor.features import FEATURE_NAMES


def _station(station_id: str, city: str = "Jersey City") -> dict:
    return {
        "station_id": station_id,
        "name": station_id,
        "city": city,
        "capacity": 20,
        "lat": 40.7,
        "lon": -74.0,
    }


def _trip(
    ride_id: str,
    started_at: str,
    ended_at: str,
    start_station: str,
    end_station: str,
    rideable_type: str = "electric_bike",
    member_casual: str = "member",
    coordinates: bool = True,
) -> dict:
    event = {
        "seq": 1,
        "type": "trip_ended",
        "ts": ended_at,
        "ride_id": ride_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_s": 1800,
        "start_station_id": start_station,
        "end_station_id": end_station,
        "rideable_type": rideable_type,
        "member_casual": member_casual,
    }
    if coordinates:
        event.update({
            "start_lat": 40.7,
            "start_lng": -74.0,
            "end_lat": 40.71,
            "end_lng": -74.0,
        })
    else:
        event.update({
            "start_lat": 40.7,
            "start_lng": -74.0,
            "end_lat": None,
            "end_lng": None,
        })
    return event


class StationFeatureTests(unittest.TestCase):
    def test_completed_rides_are_deduplicated_and_missing_energy_stays_unknown(self):
        first = _trip(
            "ride-e", "2024-03-20T05:00:00-04:00", "2024-03-20T05:30:00-04:00",
            "JC115", "JC115", coordinates=False,
        )
        duplicate = {**first, "seq": 2}
        classic = _trip(
            "ride-c", "2024-03-20T07:00:00-04:00", "2024-03-20T07:30:00-04:00",
            "HB101", "JC115", "classic_bike", "casual",
        )
        overnight = _trip(
            "ride-overnight", "2024-03-19T23:50:00-04:00", "2024-03-20T00:10:00-04:00",
            "HB101", "JC115",
        )
        status = {
            "type": "station_status",
            "ts": "2024-03-20T08:00:00-04:00",
            "station_id": "JC115",
            "num_bikes_available": 0,
            "num_docks_available": 0,
            "num_bikes_disabled": 1,
            "num_docks_disabled": 0,
        }
        rows, diagnostics = build_station_day_features(
            [first, duplicate, classic, overnight, status],
            [_station("JC115"), _station("HB101", "Hoboken")],
            date(2024, 3, 20),
            date(2024, 3, 21),
        )
        jc115 = next(row for row in rows if row["station_id"] == "JC115")
        hb101 = next(row for row in rows if row["station_id"] == "HB101")

        self.assertEqual(diagnostics["duplicate_rides"], 1)
        self.assertEqual(jc115["features"]["departures_member"], 1)
        self.assertEqual(jc115["features"]["arrivals_total"], 3)
        self.assertEqual(jc115["features"]["departures_casual"], 0)
        self.assertIsNone(jc115["features"]["energy_kwh"])
        self.assertEqual(jc115["features"]["energy_coverage"], 0)
        self.assertEqual(jc115["features"]["mean_occupancy"], 0)
        self.assertEqual(hb101["features"]["departures_casual"], 1)
        self.assertEqual(hb101["features"]["arrivals_total"], 0)

    def test_invalid_date_window_is_rejected(self):
        with self.assertRaises(ValueError):
            build_station_day_features([], [_station("JC115")], date(2024, 3, 21), date(2024, 3, 21))


class ModelTests(unittest.TestCase):
    def test_selected_model_is_serializable_and_predicts_training_rows(self):
        rows = []
        for index in range(36):
            occupancy = 0.1 if index < 18 else 0.9
            features = {name: 0.0 for name in FEATURE_NAMES}
            features.update({
                "trips_per_capacity": (index % 9) / 10,
                "mean_occupancy": occupancy,
                "p95_occupancy": occupancy,
                "departures_member": float(index % 5),
                "departures_casual": float(index % 3),
                "electric_share": 0.2 if index < 18 else 0.8,
            })
            rows.append({"station_id": f"S{index}", "features": features})
        artifact, labels, evaluation = train_model(rows)

        self.assertIn(artifact["algorithm"], ("kmeans", "gaussian_mixture"))
        self.assertEqual(len(labels), len(rows))
        self.assertGreaterEqual(artifact["cluster_count"], 2)
        self.assertEqual(len(predict_labels(artifact, rows)), len(rows))
        self.assertIn("silhouette", evaluation["selected"])
        self.assertGreaterEqual(evaluation["selected"]["minimum_cluster_share"], 5 / len(rows))


class OperationalFlagTests(unittest.TestCase):
    def test_flags_include_threshold_and_observed_values(self):
        profiles = []
        for day, occupancy in (("2024-03-20", 0.1), ("2024-03-21", 0.8)):
            for index in range(10):
                features = {name: 0.0 for name in FEATURE_NAMES}
                features.update({
                    "trips_per_capacity": index / 10,
                    "status_observations": 4.0,
                    "mean_occupancy": occupancy,
                    "empty_report_share": 0.75 if index == 0 else 0.0,
                    "full_report_share": 0.0,
                })
                profiles.append({
                    "station_id": f"S{index}",
                    "city": "Jersey City",
                    "capacity": 20,
                    "window_start": day,
                    "features": features,
                    "flags": [],
                })
        flagged = _add_flags(profiles)
        low_demand = next(
            row for row in flagged
            if row["station_id"] == "S0" and row["window_start"] == "2024-03-20"
        )
        self.assertIn("underused_relative", [flag["type"] for flag in low_demand["flags"]])
        self.assertIn("frequently_empty", [flag["type"] for flag in low_demand["flags"]])
        shifted = next(
            row for row in flagged
            if row["station_id"] == "S0" and row["window_start"] == "2024-03-21"
        )
        shift_flag = next(flag for flag in shifted["flags"] if flag["type"] == "occupancy_shift")
        self.assertEqual(shift_flag["observed"], 0.7)
        self.assertEqual(shift_flag["threshold"], 0.5)


class ProfilePersistenceTests(unittest.TestCase):
    def test_outdated_model_format_is_not_reused(self):
        self.assertFalse(_model_format_is_current({"artifact": {"format_version": 1}}))
        self.assertTrue(_model_format_is_current({
            "artifact": {"format_version": MODEL_FORMAT_VERSION}
        }))

    def test_model_and_station_day_upserts_are_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TABLE ml_models (
                        model_id TEXT PRIMARY KEY, training_start DATE, training_end DATE,
                        algorithm TEXT, cluster_count INTEGER, feature_names TEXT,
                        artifact TEXT, metrics TEXT, active INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                connection.execute(text("""
                    CREATE TABLE ml_profiles (
                        model_id TEXT, station_id TEXT, window_start DATE,
                        window_end DATE, city TEXT, capacity INTEGER, cluster_id INTEGER,
                        features TEXT, flags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (model_id, station_id, window_start)
                    )
                """))
            artifact = {
                "algorithm": "kmeans",
                "cluster_count": 2,
                "feature_names": ["trips_per_capacity"],
            }
            model = {
                "model_id": "model-1",
                "artifact": artifact,
                "algorithm": "kmeans",
                "cluster_count": 2,
            }
            evaluation = {"selected": {"silhouette": 0.25}}
            profile = {
                "station_id": "JC115",
                "window_start": "2024-03-20",
                "window_end": "2024-03-21",
                "city": "Jersey City",
                "capacity": 20,
                "cluster_id": 1,
                "features": {"trips_per_capacity": 0.1},
                "flags": [],
            }
            for _ in range(2):
                _save_model(engine, model, evaluation)
                _save_profiles(engine, "model-1", [profile])

            with engine.connect() as connection:
                model_count = connection.execute(
                    text("SELECT COUNT(*) FROM ml_models WHERE active = 1")
                ).scalar_one()
                profile_count = connection.execute(
                    text("SELECT COUNT(*) FROM ml_profiles")
                ).scalar_one()
                profile_cluster = connection.execute(
                    text("SELECT cluster_id FROM ml_profiles")
                ).scalar_one()
            self.assertEqual(model_count, 1)
            self.assertEqual(profile_count, 1)
            self.assertEqual(profile_cluster, 1)
        finally:
            engine.dispose()

    def test_profile_inputs_use_stage1_baseline_and_only_mqtt_stage2(self):
        from processor.dataset import STAGE2_SEQUENCE_START

        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                for table in ("events", "online_events"):
                    connection.execute(text(
                        f"CREATE TABLE {table} "
                        "(seq INTEGER PRIMARY KEY, type TEXT, payload TEXT)"
                    ))
                connection.execute(text(
                    "CREATE TABLE stations (station_id TEXT, payload TEXT)"
                ))
                for table, seq in (
                    ("events", 1),
                    ("events", 73580),
                    ("online_events", STAGE2_SEQUENCE_START),
                ):
                    payload = {
                        "type": "trip_ended",
                        "seq": seq,
                        "ride_id": f"ride-{seq}",
                    }
                    connection.execute(
                        text(
                            f"INSERT INTO {table} (seq, type, payload) "
                            "VALUES (:seq, 'trip_ended', :payload)"
                        ),
                        {"seq": seq, "payload": json.dumps(payload)},
                    )
                station = _station("JC115")
                connection.execute(
                    text("INSERT INTO stations VALUES (:id, :payload)"),
                    {
                        "id": station["station_id"],
                        "payload": json.dumps(station),
                    },
                )

            events, stations = _load_inputs(engine)

            self.assertEqual([event["seq"] for event in events], [1, STAGE2_SEQUENCE_START])
            self.assertEqual([station["station_id"] for station in stations], ["JC115"])
        finally:
            engine.dispose()

    def test_replacing_online_profiles_preserves_the_static_stage1_profile(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TABLE ml_profiles (
                        model_id TEXT, station_id TEXT, window_start DATE,
                        window_end DATE, city TEXT, capacity INTEGER, cluster_id INTEGER,
                        features TEXT, flags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (model_id, station_id, window_start)
                    )
                """))
                connection.execute(text("""
                    INSERT INTO ml_profiles
                        (model_id, station_id, window_start, window_end, city, capacity,
                         cluster_id, features, flags)
                    VALUES
                        ('model-1', 'JC115', '2024-03-13', '2024-03-14',
                         'Jersey City', 20, 0, '{}', '[]'),
                        ('model-1', 'JC115', '2024-03-20', '2024-03-21',
                         'Jersey City', 20, 1, '{}', '[]')
                """))

            _save_profiles(
                engine,
                "model-1",
                [{
                    "station_id": "JC115",
                    "window_start": "2024-03-13",
                    "window_end": "2024-03-14",
                    "city": "Jersey City",
                    "capacity": 20,
                    "cluster_id": 2,
                    "features": {"trips_per_capacity": 0.1},
                    "flags": [],
                }],
                replace_window=(date(2024, 3, 20), date(2024, 3, 23)),
                update_existing=False,
            )

            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT window_start, cluster_id FROM ml_profiles "
                        "WHERE model_id='model-1' ORDER BY window_start"
                    )
                ).all()
            self.assertEqual(
                [(str(row.window_start), row.cluster_id) for row in rows],
                [("2024-03-13", 0)],
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
