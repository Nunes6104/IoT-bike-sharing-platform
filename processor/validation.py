"""Validation for the supplied Citi Bike event and station records."""

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


SOURCE_OFFSET = timedelta(hours=-4)
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?-04:00$"
)


@dataclass(frozen=True)
class Issue:
    severity: str
    field: str
    message: str


def parse_source_timestamp(value: object) -> datetime:
    """Parse an explicitly offset source timestamp without changing its local time."""
    if not isinstance(value, str) or not TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError("expected an ISO 8601 timestamp with the -04:00 offset")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid ISO 8601 timestamp") from exc
    if timestamp.utcoffset() != SOURCE_OFFSET:
        raise ValueError("expected the -04:00 offset")
    return timestamp


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def parse_json_record(line: str) -> dict[str, Any]:
    """Parse a JSON object; reject non-standard NaN and Infinity values."""
    value = json.loads(line, parse_constant=_reject_json_constant)
    if not isinstance(value, dict):
        raise ValueError("record must be a JSON object")
    return value


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: object, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum <= value <= maximum
        and math.isfinite(value)
    )


def load_station_ids(path: Path) -> set[str]:
    """Load and validate station references, failing rather than ignoring bad data."""
    with path.open(encoding="utf-8-sig") as source:
        stations = json.load(source, parse_constant=_reject_json_constant)
    if not isinstance(stations, list):
        raise ValueError("station file must contain an array")
    station_ids: set[str] = set()
    for index, station in enumerate(stations, 1):
        if not isinstance(station, dict):
            raise ValueError(f"station {index}: expected an object")
        for field in ("station_id", "station_uuid", "name", "city"):
            if not _nonempty_string(station.get(field)):
                raise ValueError(f"station {index}: invalid {field}")
        station_id = station["station_id"]
        if station_id in station_ids:
            raise ValueError(f"station {index}: duplicate station_id {station_id}")
        if not _number(station.get("lat"), -90, 90):
            raise ValueError(f"station {index}: invalid lat")
        if not _number(station.get("lon"), -180, 180):
            raise ValueError(f"station {index}: invalid lon")
        capacity = station.get("capacity")
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 0:
            raise ValueError(f"station {index}: invalid capacity")
        station_ids.add(station_id)
    return station_ids


def validate_event(event: dict[str, Any], station_ids: set[str]) -> list[Issue]:
    """Return errors and data-quality warnings while leaving the payload untouched."""
    issues: list[Issue] = []

    def error(field: str, message: str) -> None:
        issues.append(Issue("error", field, message))

    def warning(field: str, message: str) -> None:
        issues.append(Issue("warning", field, message))

    def required_string(field: str) -> None:
        if not _nonempty_string(event.get(field)):
            error(field, "expected a non-empty string")

    def timestamp(field: str) -> None:
        try:
            parse_source_timestamp(event.get(field))
        except ValueError as exc:
            error(field, str(exc))

    def integer(field: str, minimum: int, maximum: int | None = None) -> None:
        value = event.get(field)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            error(field, "expected an integer in the allowed range")

    def station(field: str, nullable: bool) -> None:
        if field not in event:
            error(field, "field is missing")
        elif event[field] is None and nullable:
            warning(field, "station identifier is unavailable")
        elif not _nonempty_string(event[field]):
            error(field, "expected a non-empty station identifier")
        elif event[field] not in station_ids:
            warning(field, "station is outside the reference data")

    def coordinate(field: str, limit: int, nullable: bool) -> None:
        if field not in event:
            error(field, "field is missing")
        elif event[field] is None and nullable:
            warning(field, "coordinate is unavailable")
        elif not _number(event[field], -limit, limit):
            error(field, "expected a finite coordinate in the allowed range")

    event_type = event.get("type")
    if event_type not in ("station_status", "trip_started", "trip_ended"):
        error("type", "unknown or missing event type")
    timestamp("ts")
    integer("seq", 1)

    if event_type == "station_status":
        station("station_id", False)
        for field in (
            "num_bikes_available", "num_ebikes_available", "num_bikes_disabled",
            "num_docks_available", "num_docks_disabled",
        ):
            integer(field, 0)
        for field in ("is_installed", "is_renting", "is_returning"):
            integer(field, 0, 1)
        bikes, ebikes = event.get("num_bikes_available"), event.get("num_ebikes_available")
        if type(bikes) is int and type(ebikes) is int and ebikes > bikes:
            warning("num_ebikes_available", "electric bikes exceed available bikes")
    elif event_type in ("trip_started", "trip_ended"):
        required_string("ride_id")
        if event.get("rideable_type") not in ("classic_bike", "electric_bike"):
            error("rideable_type", "expected classic_bike or electric_bike")
        if event.get("member_casual") not in ("member", "casual"):
            error("member_casual", "expected member or casual")
        station("start_station_id", True)
        coordinate("start_lat", 90, True)
        coordinate("start_lng", 180, True)
        if event_type == "trip_ended":
            timestamp("started_at")
            timestamp("ended_at")
            integer("duration_s", 0)
            station("end_station_id", True)
            coordinate("end_lat", 90, True)
            coordinate("end_lng", 180, True)

    return issues
