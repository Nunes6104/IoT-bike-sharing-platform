"""Build auditable station/day feature rows from the observed source events."""

import json
import math
from datetime import date, timedelta
from typing import Any

from processor.calculations import estimate_energy_kwh, straight_line_distance_km
from processor.validation import parse_source_timestamp


BASE_FEATURES = (
    "trips_per_capacity",
    "departures_total",
    "arrivals_total",
    "departures_member",
    "departures_casual",
    "arrivals_member",
    "arrivals_casual",
    "net_arrivals",
    "member_share",
    "casual_share",
    "electric_share",
    "mean_duration_seconds",
    "mean_distance_km",
    "distance_coverage",
    "energy_kwh",
    "energy_coverage",
    "mean_occupancy",
    "p95_occupancy",
    "empty_report_share",
    "full_report_share",
    "mean_disabled_bikes",
    "mean_disabled_docks",
    "status_observations",
)
HOURLY_FEATURES = tuple(
    f"{direction}_{hour:02d}"
    for direction in ("departures", "arrivals")
    for hour in range(24)
)
FEATURE_NAMES = BASE_FEATURES + HOURLY_FEATURES


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _new_accumulator(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "station": station,
        "departures": 0,
        "arrivals": 0,
        "departures_member": 0,
        "departures_casual": 0,
        "arrivals_member": 0,
        "arrivals_casual": 0,
        "member_trips": 0,
        "casual_trips": 0,
        "electric_trips": 0,
        "duration_total": 0,
        "distance_values": [],
        "electric_count": 0,
        "energy_values": [],
        "status_values": [],
        "hourly_departures": [0] * 24,
        "hourly_arrivals": [0] * 24,
    }


def build_station_day_features(
    events: list[dict[str, Any]],
    stations: list[dict[str, Any]],
    start_day: date,
    end_day: date,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Create one feature row per reference station and local day in [start, end)."""
    if start_day >= end_day:
        raise ValueError("start_day must be before end_day")
    station_by_id = {station["station_id"]: station for station in stations}
    if len(station_by_id) != len(stations):
        raise ValueError("station reference contains duplicate station identifiers")

    days: list[date] = []
    current_day = start_day
    while current_day < end_day:
        days.append(current_day)
        current_day += timedelta(days=1)

    accumulators = {
        (station_id, day): _new_accumulator(station)
        for day in days
        for station_id, station in station_by_id.items()
    }
    status_counts = {"unknown_station_status": 0, "unknown_trip_start": 0,
                     "unknown_trip_end": 0, "duplicate_rides": 0,
                     "conflicting_rides": 0}
    rides: dict[str, dict[str, Any]] = {}
    conflicting_rides: set[str] = set()

    for event in events:
        event_type = event.get("type")
        if event_type == "station_status":
            timestamp = parse_source_timestamp(event.get("ts"))
            day = timestamp.date()
            station_id = event.get("station_id")
            if day not in days:
                continue
            if station_id not in station_by_id:
                status_counts["unknown_station_status"] += 1
                continue
            accumulator = accumulators[(station_id, day)]
            capacity = station_by_id[station_id]["capacity"]
            bikes = _finite_number(event.get("num_bikes_available"))
            if capacity > 0 and bikes is not None:
                accumulator["status_values"].append({
                    "occupancy": bikes / capacity,
                    "empty": bikes == 0,
                    "full": event.get("num_docks_available") == 0,
                    "disabled_bikes": _finite_number(event.get("num_bikes_disabled")),
                    "disabled_docks": _finite_number(event.get("num_docks_disabled")),
                })
            continue

        if event_type != "trip_ended":
            continue
        ride_id = event.get("ride_id")
        if not isinstance(ride_id, str) or not ride_id:
            continue
        fingerprint = json.dumps(
            {key: value for key, value in event.items() if key != "seq"},
            sort_keys=True,
            separators=(",", ":"),
        )
        previous = rides.get(ride_id)
        if previous is not None:
            if previous["fingerprint"] != fingerprint:
                conflicting_rides.add(ride_id)
            else:
                status_counts["duplicate_rides"] += 1
            continue
        rides[ride_id] = {"event": event, "fingerprint": fingerprint}

    status_counts["conflicting_rides"] = len(conflicting_rides)
    for ride_id, record in rides.items():
        if ride_id in conflicting_rides:
            continue
        event = record["event"]
        started_at = parse_source_timestamp(event.get("started_at"))
        ended_at = parse_source_timestamp(event.get("ended_at"))
        start_station_id = event.get("start_station_id")
        end_station_id = event.get("end_station_id")
        ride_type = event.get("rideable_type")
        user_type = event.get("member_casual")
        duration = event.get("duration_s")
        distance = straight_line_distance_km(event)
        energy = estimate_energy_kwh(event)

        if start_station_id in station_by_id and started_at.date() in days:
            accumulator = accumulators[(start_station_id, started_at.date())]
            accumulator["departures"] += 1
            accumulator[f"departures_{user_type}"] += 1
            accumulator["hourly_departures"][started_at.hour] += 1
            accumulator["member_trips"] += user_type == "member"
            accumulator["casual_trips"] += user_type == "casual"
            accumulator["electric_trips"] += ride_type == "electric_bike"
            accumulator["duration_total"] += duration
            accumulator["electric_count"] += ride_type == "electric_bike"
            if distance is not None:
                accumulator["distance_values"].append(distance)
            if ride_type == "electric_bike" and energy is not None:
                accumulator["energy_values"].append(float(energy))
        elif started_at.date() in days:
            status_counts["unknown_trip_start"] += 1

        if end_station_id in station_by_id and ended_at.date() in days:
            accumulator = accumulators[(end_station_id, ended_at.date())]
            accumulator["arrivals"] += 1
            accumulator[f"arrivals_{user_type}"] += 1
            accumulator["hourly_arrivals"][ended_at.hour] += 1
        elif ended_at.date() in days:
            status_counts["unknown_trip_end"] += 1

    rows = []
    for day in days:
        for station_id, station in station_by_id.items():
            accumulator = accumulators[(station_id, day)]
            departures = accumulator["departures"]
            arrivals = accumulator["arrivals"]
            capacity = station["capacity"]
            statuses = accumulator["status_values"]
            occupancies = sorted(value["occupancy"] for value in statuses)
            known_distance = accumulator["distance_values"]
            known_energy = accumulator["energy_values"]
            electric_count = accumulator["electric_count"]
            trip_count = accumulator["member_trips"] + accumulator["casual_trips"]
            features: dict[str, float | None] = {
                "trips_per_capacity": (
                    departures / capacity if capacity > 0 else None
                ),
                "departures_total": float(departures),
                "arrivals_total": float(arrivals),
                "departures_member": float(accumulator["departures_member"]),
                "departures_casual": float(accumulator["departures_casual"]),
                "arrivals_member": float(accumulator["arrivals_member"]),
                "arrivals_casual": float(accumulator["arrivals_casual"]),
                "net_arrivals": arrivals - departures,
                "member_share": (
                    accumulator["member_trips"] / trip_count if trip_count else None
                ),
                "casual_share": (
                    accumulator["casual_trips"] / trip_count if trip_count else None
                ),
                "electric_share": (
                    accumulator["electric_trips"] / trip_count if trip_count else None
                ),
                "mean_duration_seconds": (
                    accumulator["duration_total"] / departures if departures else None
                ),
                "mean_distance_km": (
                    sum(known_distance) / len(known_distance) if known_distance else None
                ),
                "distance_coverage": (
                    len(known_distance) / departures if departures else None
                ),
                "energy_kwh": sum(known_energy) if known_energy else (
                    0.0 if departures and not electric_count else None
                ),
                "energy_coverage": (
                    len(known_energy) / electric_count if electric_count else None
                ),
                "mean_occupancy": (
                    sum(occupancies) / len(occupancies) if occupancies else None
                ),
                "p95_occupancy": (
                    occupancies[min(len(occupancies) - 1, math.ceil(len(occupancies) * 0.95) - 1)]
                    if occupancies else None
                ),
                "empty_report_share": (
                    sum(value["empty"] for value in statuses) / len(statuses)
                    if statuses else None
                ),
                "full_report_share": (
                    sum(value["full"] for value in statuses) / len(statuses)
                    if statuses else None
                ),
                "mean_disabled_bikes": _mean_optional(statuses, "disabled_bikes"),
                "mean_disabled_docks": _mean_optional(statuses, "disabled_docks"),
                "status_observations": float(len(statuses)),
            }
            for hour in range(24):
                features[f"departures_{hour:02d}"] = float(
                    accumulator["hourly_departures"][hour]
                )
                features[f"arrivals_{hour:02d}"] = float(
                    accumulator["hourly_arrivals"][hour]
                )
            rows.append({
                "station_id": station_id,
                "station_name": station.get("name"),
                "city": station.get("city"),
                "capacity": capacity,
                "window_start": day.isoformat(),
                "window_end": (day + timedelta(days=1)).isoformat(),
                "features": features,
            })
    return rows, status_counts


def _mean_optional(statuses: list[dict[str, Any]], key: str) -> float | None:
    values = [value[key] for value in statuses if value[key] is not None]
    return sum(values) / len(values) if values else None
