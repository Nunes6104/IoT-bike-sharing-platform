"""Coherent latest-station snapshots for the operator map."""

import json
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, text

from processor.dataset import STAGE2_SEQUENCE_START


_SNAPSHOT_QUERY = """
    WITH source_events AS (
        SELECT seq, type, ts_utc, payload, validation_status, validation_reason
        FROM events
        WHERE seq < :stage2_sequence_start
        UNION ALL
        SELECT seq, type, ts_utc, payload, validation_status, validation_reason
        FROM online_events
    ),
    ranked_statuses AS (
        SELECT
            e.seq,
            e.ts_utc,
            e.payload,
            e.validation_status,
            e.validation_reason,
            {station_id_expression} AS station_id,
            ROW_NUMBER() OVER (
                PARTITION BY {station_id_expression}
                ORDER BY e.ts_utc DESC, e.seq DESC
            ) AS rank_order
        FROM source_events AS e
        WHERE e.type = 'station_status'
          AND e.validation_status != 'rejected'
    ),
    latest_event AS (
        SELECT MAX(ts_utc) AS event_time FROM source_events
        WHERE validation_status != 'rejected'
    )
    SELECT
        s.station_id AS reference_station_id,
        s.payload AS station_payload,
        r.seq,
        r.ts_utc AS status_ts_utc,
        r.payload AS status_payload,
        r.validation_status,
        r.validation_reason,
        latest_event.event_time AS latest_event_time
    FROM latest_event
    LEFT JOIN stations AS s ON 1 = 1
    LEFT JOIN ranked_statuses AS r
        ON r.station_id = s.station_id AND r.rank_order = 1
    ORDER BY s.station_id
    """

_ACTIVE_TRIPS_QUERY = """
    WITH ranked_trip_events AS (
        SELECT
            e.seq,
            e.type,
            e.ts_utc,
            e.payload,
            e.validation_status,
            e.validation_reason,
            {ride_id_expression} AS ride_id,
            ROW_NUMBER() OVER (
                PARTITION BY {ride_id_expression}
                ORDER BY e.seq DESC
            ) AS rank_order
        FROM online_events AS e
        WHERE e.type IN ('trip_started', 'trip_ended')
          AND e.validation_status != 'rejected'
          AND e.seq >= :stage2_sequence_start
    )
    SELECT
        seq,
        payload,
        validation_status,
        validation_reason,
        ride_id
    FROM ranked_trip_events
    WHERE rank_order = 1
      AND type = 'trip_started'
      AND ride_id IS NOT NULL
    ORDER BY seq DESC
    """


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _valid_coordinates(station: dict[str, Any]) -> bool:
    lat, lon = station.get("lat"), station.get("lon")
    return (
        isinstance(lat, (int, float))
        and not isinstance(lat, bool)
        and math.isfinite(lat)
        and -90 <= lat <= 90
        and isinstance(lon, (int, float))
        and not isinstance(lon, bool)
        and math.isfinite(lon)
        and -180 <= lon <= 180
    )


def _validation_warnings(reason: str | None) -> list[dict[str, str]]:
    try:
        return json.loads(reason) if reason else []
    except (TypeError, ValueError):
        return [{
            "severity": "warning",
            "field": "validation_reason",
            "message": "Stored validation details could not be parsed",
        }]


class StationSnapshotService:
    """Return reference stations with their latest committed status reports."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def latest(self) -> dict[str, Any]:
        """Read reference stations, statuses, and metadata in one SQL snapshot."""
        with self.engine.connect() as connection:
            if self.engine.dialect.name == "mysql":
                connection.execute(text("SET SESSION time_zone='+00:00'"))
            station_id_expression = (
                "JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.station_id'))"
                if self.engine.dialect.name == "mysql"
                else "json_extract(e.payload, '$.station_id')"
            )
            ride_id_expression = (
                "JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.ride_id'))"
                if self.engine.dialect.name == "mysql"
                else "json_extract(e.payload, '$.ride_id')"
            )
            rows = connection.execute(
                text(_SNAPSHOT_QUERY.format(
                    station_id_expression=station_id_expression
                )),
                {"stage2_sequence_start": STAGE2_SEQUENCE_START},
            ).all()
            active_trip_rows = connection.execute(
                text(_ACTIVE_TRIPS_QUERY.format(
                    ride_id_expression=ride_id_expression
                )),
                {"stage2_sequence_start": STAGE2_SEQUENCE_START},
            ).all()

        latest_event_at = rows[0].latest_event_time if rows else None
        active_trips = []
        for row in active_trip_rows:
            payload = json.loads(row.payload)
            active_trips.append({
                "ride_id": row.ride_id,
                "seq": row.seq,
                "started_at": payload.get("ts"),
                "start_station_id": payload.get("start_station_id"),
                "rideable_type": payload.get("rideable_type"),
                "member_casual": payload.get("member_casual"),
                "validation_status": row.validation_status,
                "warnings": _validation_warnings(row.validation_reason),
            })

        stations = []
        for row in rows:
            if row.reference_station_id is None:
                continue
            reference = json.loads(row.station_payload)
            station_id = row.reference_station_id
            status = None
            if row.seq is not None:
                payload = json.loads(row.status_payload)
                status = {
                    "seq": row.seq,
                    "reported_at": payload.get("ts"),
                    "event_time_utc": _iso_utc(row.status_ts_utc),
                    "validation_status": row.validation_status,
                    "num_bikes_available": payload.get("num_bikes_available"),
                    "num_ebikes_available": payload.get("num_ebikes_available"),
                    "num_bikes_disabled": payload.get("num_bikes_disabled"),
                    "num_docks_available": payload.get("num_docks_available"),
                    "num_docks_disabled": payload.get("num_docks_disabled"),
                    "is_installed": payload.get("is_installed"),
                    "is_renting": payload.get("is_renting"),
                    "is_returning": payload.get("is_returning"),
                    "warnings": _validation_warnings(row.validation_reason),
                }
            stations.append({
                "station_id": station_id,
                "name": reference.get("name"),
                "lat": reference.get("lat"),
                "lon": reference.get("lon"),
                "capacity": reference.get("capacity"),
                "city": reference.get("city"),
                "mappable": _valid_coordinates(reference),
                "status": status,
            })

        return {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "latest_committed_event_at": _iso_utc(latest_event_at),
            "active_trips": active_trips,
            "stations": stations,
        }
