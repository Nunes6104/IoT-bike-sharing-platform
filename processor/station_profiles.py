"""Read bounded, versioned station-profile results for the operator API."""

import json
from datetime import date
from typing import Any

from sqlalchemy import Engine, text


MAX_PROFILE_RANGE_DAYS = 31


class StationProfileService:
    """Query the currently active model and its daily profile snapshots."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def model(self) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT model_id, training_start, training_end, algorithm, "
                    "cluster_count, feature_names, metrics, created_at "
                    "FROM ml_models WHERE active = 1 "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            ).first()
        if row is None:
            return None
        return {
            "model_id": row.model_id,
            "training_start": _date_string(row.training_start),
            "training_end": _date_string(row.training_end),
            "algorithm": row.algorithm,
            "cluster_count": row.cluster_count,
            "feature_names": json.loads(row.feature_names),
            "metrics": json.loads(row.metrics),
            "created_at": str(row.created_at),
        }

    def profiles(self, start: str, end: str) -> dict[str, Any]:
        start_day, end_day = _parse_range(start, end)
        model = self.model()
        if model is None:
            return {"model": None, "profiles": [], "evolution": [], "flags": []}
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT station_id, window_start, window_end, city, capacity, "
                    "cluster_id, features, flags FROM ml_profiles "
                    "WHERE model_id = :model_id AND window_start >= :start "
                    "AND window_start < :end ORDER BY window_start, city, station_id"
                ),
                {
                    "model_id": model["model_id"],
                    "start": start_day,
                    "end": end_day,
                },
            )
            profiles = [
                {
                    "station_id": row.station_id,
                    "window_start": _date_string(row.window_start),
                    "window_end": _date_string(row.window_end),
                    "city": row.city,
                    "capacity": row.capacity,
                    "cluster_id": row.cluster_id,
                    "features": json.loads(row.features),
                    "flags": json.loads(row.flags),
                }
                for row in rows
            ]
        evolution = _cluster_evolution(profiles)
        flags = [
            {
                "station_id": profile["station_id"],
                "window_start": profile["window_start"],
                "city": profile["city"],
                **flag,
            }
            for profile in profiles
            for flag in profile["flags"]
        ]
        return {
            "model": model,
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
            "profiles": profiles,
            "evolution": evolution,
            "flags": flags,
        }


def _parse_range(start: str, end: str) -> tuple[date, date]:
    try:
        start_day = date.fromisoformat(start)
        end_day = date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise ValueError("start and end must be ISO dates (YYYY-MM-DD)") from exc
    if start_day.isoformat() != start or end_day.isoformat() != end:
        raise ValueError("start and end must be ISO dates (YYYY-MM-DD)")
    days = (end_day - start_day).days
    if days <= 0 or days > MAX_PROFILE_RANGE_DAYS:
        raise ValueError("profile date range must be 1 to 31 days; end is exclusive")
    return start_day, end_day


def _date_string(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _cluster_evolution(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, int], int] = {}
    for profile in profiles:
        key = (profile["window_start"], profile["cluster_id"])
        counts[key] = counts.get(key, 0) + 1
    return [
        {"window_start": day, "cluster_id": cluster, "station_count": count}
        for (day, cluster), count in sorted(counts.items())
    ]
