"""Create explainable station flags and persist versioned profile results."""

import hashlib
import json
import logging
import math
import os
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Engine, text

from ml_processor.features import build_station_day_features
from ml_processor.modeling import (
    MODEL_FORMAT_VERSION,
    predict_labels,
    train_model,
)
from processor.dataset import STAGE2_SEQUENCE_START
from processor.validation import parse_json_record, parse_source_timestamp


LOGGER = logging.getLogger("ml_processor")
TRAIN_START = date(2024, 3, 13)
TRAIN_END = date(2024, 3, 20)
STAGE2_START = date(2024, 3, 20)
STAGE2_END = date(2024, 3, 23)
UNDERUSE_PERCENTILE = 0.10
MIN_STATUS_OBSERVATIONS = 4
OCCUPANCY_SHARE_LIMIT = 0.50
OCCUPANCY_SHIFT_LIMIT = 0.50


def refresh_profiles(engine: Engine) -> dict[str, Any]:
    """Train once from Stage 1 and idempotently refresh available daily profiles."""
    events, stations = _load_inputs(engine)
    if not stations:
        raise RuntimeError("no station reference records are available")
    training_events = [
        event for event in events
        if isinstance(event.get("seq"), int) and event["seq"] < STAGE2_SEQUENCE_START
    ]
    online_events = [
        event for event in events
        if isinstance(event.get("seq"), int) and event["seq"] >= STAGE2_SEQUENCE_START
    ]

    active_model = _load_active_model(engine)
    if active_model is not None and not _model_format_is_current(active_model):
        LOGGER.warning(
            "Active model format %s is outdated; training a replacement from Stage 1",
            active_model["artifact"].get("format_version"),
        )
        active_model = None
    training_rows, training_diagnostics = build_station_day_features(
        training_events, stations, TRAIN_START, TRAIN_END
    )
    if active_model is None:
        artifact, labels, evaluation = train_model(training_rows)
        model_id = hashlib.sha256(
            json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        active_model = {
            "model_id": model_id,
            "artifact": artifact,
            "algorithm": artifact["algorithm"],
            "cluster_count": artifact["cluster_count"],
        }
        _save_model(engine, active_model, evaluation)
        LOGGER.info(
            "Trained station model id=%s algorithm=%s clusters=%s profiles=%s",
            model_id,
            artifact["algorithm"],
            artifact["cluster_count"],
            evaluation["profile_count"],
        )
    else:
        labels = predict_labels(active_model["artifact"], training_rows)
        evaluation = None

    training_profiles = _assign(training_rows, labels, active_model["model_id"])
    online_end = _latest_online_day(online_events)
    online_count = 0
    online_profiles = []
    if online_end is not None:
        stage2_end = min(online_end + timedelta(days=1), STAGE2_END)
        if stage2_end > STAGE2_START:
            online_rows, online_diagnostics = build_station_day_features(
                online_events, stations, STAGE2_START, stage2_end
            )
            online_labels = predict_labels(active_model["artifact"], online_rows)
            online_profiles = _assign(
                online_rows, online_labels, active_model["model_id"]
            )
            online_count = len(online_profiles)
            LOGGER.info(
                "Prepared online profiles rows=%s range=%s..%s diagnostics=%s",
                online_count,
                STAGE2_START,
                stage2_end - timedelta(days=1),
                online_diagnostics,
            )

    flagged_profiles = _add_flags(training_profiles + online_profiles)
    training_profiles = flagged_profiles[:len(training_profiles)]
    online_profiles = flagged_profiles[len(training_profiles):]
    _save_profiles(
        engine,
        active_model["model_id"],
        training_profiles,
        replace_window=(STAGE2_START, STAGE2_END),
        update_existing=False,
    )
    if online_profiles:
        _save_profiles(engine, active_model["model_id"], online_profiles)

    LOGGER.info(
        "Profile refresh complete model=%s training_rows=%s online_rows=%s "
        "training_diagnostics=%s",
        active_model["model_id"],
        len(training_profiles),
        online_count,
        training_diagnostics,
    )
    return {
        "model_id": active_model["model_id"],
        "algorithm": active_model["algorithm"],
        "cluster_count": active_model["cluster_count"],
        "training_rows": len(training_profiles),
        "online_rows": online_count,
        "evaluation": evaluation,
    }


def _load_inputs(engine: Engine) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with engine.connect() as connection:
        event_rows = connection.execute(
            text(
                "SELECT payload FROM events "
                "WHERE seq < :stage2_sequence_start "
                "AND type IN ('station_status', 'trip_ended') ORDER BY seq"
            ),
            {"stage2_sequence_start": STAGE2_SEQUENCE_START},
        ).all()
        events = [parse_json_record(row.payload) for row in event_rows]
        online_rows = connection.execute(
            text(
                "SELECT payload FROM online_events "
                "WHERE type IN ('station_status', 'trip_ended') ORDER BY seq"
            )
        ).all()
        events.extend(parse_json_record(row.payload) for row in online_rows)
        station_rows = connection.execute(
            text("SELECT payload FROM stations ORDER BY station_id")
        )
        stations = [parse_json_record(row.payload) for row in station_rows]
    return events, stations


def _load_active_model(engine: Engine) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT model_id, algorithm, cluster_count, artifact "
                "FROM ml_models WHERE active = 1 ORDER BY created_at DESC LIMIT 1"
            )
        ).first()
    if row is None:
        return None
    return {
        "model_id": row.model_id,
        "algorithm": row.algorithm,
        "cluster_count": row.cluster_count,
        "artifact": json.loads(row.artifact),
    }


def _model_format_is_current(model: dict[str, Any]) -> bool:
    return model["artifact"].get("format_version") == MODEL_FORMAT_VERSION


def _save_model(
    engine: Engine, model: dict[str, Any], evaluation: dict[str, Any]
) -> None:
    artifact = model["artifact"]
    upsert = (
        "ON DUPLICATE KEY UPDATE active = 1"
        if engine.dialect.name == "mysql"
        else "ON CONFLICT(model_id) DO UPDATE SET active = 1"
    )
    statement = text(
        "INSERT INTO ml_models "
        "(model_id, training_start, training_end, algorithm, cluster_count, "
        "feature_names, artifact, metrics, active) "
        "VALUES (:model_id, :start, :end, :algorithm, :clusters, :features, "
        f":artifact, :metrics, 1) {upsert}"
    )
    serialized_evaluation = json.dumps(evaluation, separators=(",", ":"))
    with engine.begin() as connection:
        connection.execute(text("UPDATE ml_models SET active = 0 WHERE active = 1"))
        connection.execute(
            statement,
            {
                "model_id": model["model_id"],
                "start": TRAIN_START,
                "end": TRAIN_END,
                "algorithm": model["algorithm"],
                "clusters": model["cluster_count"],
                "features": json.dumps(artifact["feature_names"]),
                "artifact": json.dumps(artifact, separators=(",", ":")),
                "metrics": serialized_evaluation,
            },
        )


def _assign(
    rows: list[dict[str, Any]], labels: list[int], model_id: str
) -> list[dict[str, Any]]:
    if len(rows) != len(labels):
        raise ValueError("model returned a different number of labels than profiles")
    return [
        {
            **row,
            "model_id": model_id,
            "cluster_id": label,
            "flags": [],
        }
        for row, label in zip(rows, labels)
    ]


def _add_flags(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag relative low turnover, frequent empty/full reports, and occupancy shifts."""
    settings = _flag_settings()
    by_day_city: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_station_day = {
        (profile["station_id"], profile["window_start"]): profile for profile in profiles
    }
    for profile in profiles:
        by_day_city.setdefault(
            (profile["window_start"], profile.get("city") or ""), []
        ).append(profile)

    for key, peer_profiles in by_day_city.items():
        city = key[1]
        scores = sorted(
            profile["features"]["trips_per_capacity"]
            for profile in peer_profiles
            if profile["capacity"] > 0
            and profile["features"]["trips_per_capacity"] is not None
        )
        if scores:
            index = max(
                0, math.ceil(len(scores) * settings["underuse_percentile"]) - 1
            )
            threshold = scores[index]
            for profile in peer_profiles:
                score = profile["features"]["trips_per_capacity"]
                if (
                    profile["capacity"] > 0
                    and score is not None
                    and score <= threshold
                ):
                    profile["flags"].append({
                        "type": "underused_relative",
                        "severity": "info",
                        "observed": round(score, 6),
                        "threshold": round(threshold, 6),
                        "basis": f"at or below the {settings['underuse_percentile']:.0%} "
                                 f"city peer percentile for trips per dock per day ({city})",
                    })

    for profile in profiles:
        features = profile["features"]
        if features["status_observations"] >= settings["minimum_status_observations"]:
            for kind in ("empty", "full"):
                share = features[f"{kind}_report_share"]
                if share is not None and share >= settings["occupancy_share_limit"]:
                    profile["flags"].append({
                        "type": f"frequently_{kind}",
                        "severity": "warning",
                        "observed": round(share, 6),
                        "threshold": settings["occupancy_share_limit"],
                        "basis": (
                            f"at least {settings['occupancy_share_limit']:.0%} of "
                            f"{int(features['status_observations'])} valid daily "
                            "status observations"
                        ),
                    })
        previous_day = (
            date.fromisoformat(profile["window_start"]) - timedelta(days=1)
        ).isoformat()
        previous = by_station_day.get((profile["station_id"], previous_day))
        occupancy = features["mean_occupancy"]
        if previous is not None and occupancy is not None:
            previous_features = previous["features"]
            previous_occupancy = previous_features["mean_occupancy"]
            if (
                previous_occupancy is not None
                and features["status_observations"] >= settings["minimum_status_observations"]
                and previous_features["status_observations"] >= settings["minimum_status_observations"]
                and abs(occupancy - previous_occupancy) >= settings["occupancy_shift_limit"]
            ):
                profile["flags"].append({
                    "type": "occupancy_shift",
                    "severity": "warning",
                    "observed": round(occupancy - previous_occupancy, 6),
                    "threshold": settings["occupancy_shift_limit"],
                    "basis": (
                        "absolute change in mean reported occupancy from the "
                        "previous local day"
                    ),
                })
    return profiles


def _flag_settings() -> dict[str, float | int]:
    settings: dict[str, float | int] = {
        "underuse_percentile": float(os.environ.get("ML_UNDERUSE_PERCENTILE", "0.10")),
        "minimum_status_observations": int(
            os.environ.get("ML_MIN_STATUS_OBSERVATIONS", "4")
        ),
        "occupancy_share_limit": float(
            os.environ.get("ML_OCCUPANCY_SHARE_LIMIT", "0.50")
        ),
        "occupancy_shift_limit": float(
            os.environ.get("ML_OCCUPANCY_SHIFT_LIMIT", "0.50")
        ),
    }
    if not 0 < settings["underuse_percentile"] <= 0.5:
        raise ValueError("ML_UNDERUSE_PERCENTILE must be above 0 and at most 0.5")
    if not 1 <= settings["minimum_status_observations"] <= 100:
        raise ValueError("ML_MIN_STATUS_OBSERVATIONS must be between 1 and 100")
    if not 0 < settings["occupancy_share_limit"] <= 1:
        raise ValueError("ML_OCCUPANCY_SHARE_LIMIT must be above 0 and at most 1")
    if not 0 < settings["occupancy_shift_limit"] <= 1:
        raise ValueError("ML_OCCUPANCY_SHIFT_LIMIT must be above 0 and at most 1")
    return settings


def _save_profiles(
    engine: Engine,
    model_id: str,
    profiles: list[dict[str, Any]],
    *,
    replace_window: tuple[date, date] | None = None,
    update_existing: bool = True,
) -> None:
    upsert = (
        "ON DUPLICATE KEY UPDATE city = VALUES(city), capacity = VALUES(capacity), "
        "cluster_id = VALUES(cluster_id), features = VALUES(features), "
        "flags = VALUES(flags), updated_at = CURRENT_TIMESTAMP"
        if engine.dialect.name == "mysql"
        else "ON CONFLICT(model_id, station_id, window_start) DO UPDATE SET "
        "city = excluded.city, capacity = excluded.capacity, "
        "cluster_id = excluded.cluster_id, features = excluded.features, "
        "flags = excluded.flags, updated_at = CURRENT_TIMESTAMP"
    )
    if not update_existing:
        upsert = ""
    insert = (
        "INSERT INTO" if update_existing else "INSERT IGNORE INTO"
    ) if engine.dialect.name == "mysql" else (
        "INSERT INTO" if update_existing else "INSERT OR IGNORE INTO"
    )
    statement = text(
        f"{insert} ml_profiles "
        "(model_id, station_id, window_start, window_end, city, capacity, "
        "cluster_id, features, flags) "
        "VALUES (:model_id, :station_id, :window_start, :window_end, :city, "
        f":capacity, :cluster_id, :features, :flags) {upsert}"
    )
    with engine.begin() as connection:
        if replace_window is not None:
            connection.execute(
                text(
                    "DELETE FROM ml_profiles WHERE model_id = :model_id "
                    "AND window_start >= :start AND window_start < :end"
                ),
                {
                    "model_id": model_id,
                    "start": replace_window[0],
                    "end": replace_window[1],
                },
            )
        for profile in profiles:
            connection.execute(
                statement,
                {
                    "model_id": model_id,
                    "station_id": profile["station_id"],
                    "window_start": date.fromisoformat(profile["window_start"]),
                    "window_end": date.fromisoformat(profile["window_end"]),
                    "city": profile.get("city"),
                    "capacity": profile["capacity"],
                    "cluster_id": profile["cluster_id"],
                    "features": json.dumps(profile["features"], separators=(",", ":")),
                    "flags": json.dumps(profile["flags"], separators=(",", ":")),
                },
            )


def _latest_online_day(events: list[dict[str, Any]]) -> date | None:
    online_days = []
    for event in events:
        try:
            source_day = parse_source_timestamp(event.get("ts")).date()
        except ValueError:
            continue
        if STAGE2_START <= source_day < STAGE2_END:
            online_days.append(source_day)
    return max(online_days) if online_days else None


def refresh_interval_seconds() -> int:
    """Read the explicit bounded polling interval used by the standalone service."""
    value = int(os.environ.get("ML_REFRESH_SECONDS", "60"))
    if not 5 <= value <= 3600:
        raise ValueError("ML_REFRESH_SECONDS must be between 5 and 3600")
    return value
