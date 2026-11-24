"""Historical analytics over the persisted station and trip events."""

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, text

from processor.calculations import estimate_energy_kwh, estimate_fare_usd
from processor.validation import parse_json_record, parse_source_timestamp


LOCAL_TZ = timezone(timedelta(hours=-4))
MAX_RANGE = timedelta(days=31)
TIME_PERIODS = (
    ("night", 0, 6),
    ("morning", 6, 12),
    ("afternoon", 12, 18),
    ("evening", 18, 24),
)


def parse_local_range(start: str, end: str) -> tuple[datetime, datetime]:
    """Validate a half-open range expressed using the source's explicit -04:00 offset."""
    start_time = parse_source_timestamp(start)
    end_time = parse_source_timestamp(end)
    if start_time >= end_time:
        raise ValueError("start must be earlier than end")
    if end_time - start_time > MAX_RANGE:
        raise ValueError("the requested range cannot exceed 31 days")
    return start_time, end_time


def _bucket_start(value: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "week":
        local_day = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return local_day - timedelta(days=local_day.weekday())
    raise ValueError("bucket must be hour, day, or week")


def _next_bucket(value: datetime, bucket: str) -> datetime:
    return value + {
        "hour": timedelta(hours=1),
        "day": timedelta(days=1),
        "week": timedelta(days=7),
    }[bucket]


def _bucket_label(value: datetime, bucket: str) -> str:
    if bucket == "hour":
        return value.isoformat(timespec="minutes")
    return value.date().isoformat()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _decimal(value: Decimal, places: int = 6) -> str:
    return format(value, f".{places}f")


class AnalyticsService:
    """Build bounded, local-time summaries without treating unknown data as zero."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def summarize(self, start: str, end: str, bucket: str = "day") -> dict[str, Any]:
        """Return Stage 1 metrics for the half-open local time range [start, end)."""
        start_time, end_time = parse_local_range(start, end)
        if bucket not in ("hour", "day", "week"):
            raise ValueError("bucket must be hour, day, or week")
        start_utc = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = end_time.astimezone(timezone.utc).replace(tzinfo=None)

        with self.engine.connect() as connection:
            if self.engine.dialect.name == "mysql":
                connection.execute(text("SET SESSION time_zone='+00:00'"))
            trip_rows = connection.execute(
                text("SELECT payload, validation_status FROM events WHERE type='trip_ended'")
            )
            station_rows = connection.execute(
                text(
                    "SELECT payload FROM events "
                    "WHERE type='station_status' AND ts_utc >= :start AND ts_utc < :end"
                ),
                {"start": start_utc, "end": end_utc},
            )
            reference_rows = connection.execute(text("SELECT payload FROM stations"))

            trips = [
                (parse_json_record(row.payload), row.validation_status)
                for row in trip_rows
            ]
            statuses = [parse_json_record(row.payload) for row in station_rows]
            station_records = [json.loads(row.payload) for row in reference_rows]

        bins: dict[str, dict[str, Any]] = {}
        cursor = _bucket_start(start_time, bucket)
        while cursor < end_time:
            bins[_bucket_label(cursor, bucket)] = {
                "trips": 0,
                "member_trips": 0,
                "casual_trips": 0,
                "fare_usd": Decimal("0"),
                "member_fare_usd": Decimal("0"),
                "casual_fare_usd": Decimal("0"),
                "energy_kwh_known": Decimal("0"),
                "energy_unknown_trips": 0,
                "duration_seconds_total": 0,
            }
            cursor = _next_bucket(cursor, bucket)

        metrics: dict[str, dict[str, Any]] = {
            station["station_id"]: {
                "station_id": station["station_id"],
                "station_name": station["name"],
                "capacity": station["capacity"],
                "departures": Counter(),
                "arrivals": Counter(),
                "observed_status_updates": 0,
                "empty_updates": 0,
                "full_updates": 0,
            }
            for station in station_records
        }

        ride_records: dict[str, dict[str, Any]] = {}
        duplicate_rides = 0
        conflicting_rides = 0
        warning_trips = 0
        time_of_day: Counter[str] = Counter()
        total_duration = 0
        total_fare = Decimal("0")
        fares_by_user_type = {"member": Decimal("0"), "casual": Decimal("0")}
        known_energy = Decimal("0")
        unknown_energy = 0
        energy_applicable = 0

        for event, validation_status in trips:
            ride_id = event.get("ride_id")
            started_at = parse_source_timestamp(event["started_at"])
            if not start_time <= started_at < end_time:
                continue
            fingerprint = {key: value for key, value in event.items() if key != "seq"}
            if ride_id in ride_records:
                previous = ride_records[ride_id]
                duplicate_rides += 1
                if previous != fingerprint:
                    conflicting_rides += 1
                continue
            ride_records[ride_id] = fingerprint

            label = _bucket_label(_bucket_start(started_at, bucket), bucket)
            point = bins[label]
            user_type = event["member_casual"]
            duration = event["duration_s"]
            fare = estimate_fare_usd(duration, user_type, event["rideable_type"])
            energy = estimate_energy_kwh(event)

            point["trips"] += 1
            point[f"{user_type}_trips"] += 1
            point["fare_usd"] += fare
            point[f"{user_type}_fare_usd"] += fare
            point["duration_seconds_total"] += duration
            total_duration += duration
            total_fare += fare
            fares_by_user_type[user_type] += fare
            if event["rideable_type"] == "electric_bike":
                energy_applicable += 1
                if energy is None:
                    point["energy_unknown_trips"] += 1
                    unknown_energy += 1
                else:
                    point["energy_kwh_known"] += energy
                    known_energy += energy
            period = next(
                name for name, lower, upper in TIME_PERIODS
                if lower <= started_at.hour < upper
            )
            time_of_day[period] += 1
            if validation_status == "warning":
                warning_trips += 1

            start_station = event.get("start_station_id")
            end_station = event.get("end_station_id")
            if start_station in metrics:
                metrics[start_station]["departures"][user_type] += 1
            if end_station in metrics:
                metrics[end_station]["arrivals"][user_type] += 1

        for event in statuses:
            station_id = event["station_id"]
            if station_id not in metrics:
                continue
            row = metrics[station_id]
            row["observed_status_updates"] += 1
            row["empty_updates"] += event["num_bikes_available"] == 0
            row["full_updates"] += event["num_docks_available"] == 0

        station_utilization = []
        for station in metrics.values():
            observed = station.pop("observed_status_updates")
            empty = station.pop("empty_updates")
            full = station.pop("full_updates")
            departures = station.pop("departures")
            arrivals = station.pop("arrivals")
            station_utilization.append({
                **station,
                "departures_member": departures["member"],
                "departures_casual": departures["casual"],
                "arrivals_member": arrivals["member"],
                "arrivals_casual": arrivals["casual"],
                "observed_status_updates": observed,
                "empty_updates": empty,
                "full_updates": full,
                "empty_update_share": round(empty / observed, 4) if observed else None,
                "full_update_share": round(full / observed, 4) if observed else None,
            })
        station_utilization.sort(
            key=lambda row: (
                row["departures_member"] + row["departures_casual"],
                row["arrivals_member"] + row["arrivals_casual"],
            ),
            reverse=True,
        )

        trends = []
        for label, point in bins.items():
            point["fare_usd"] = _money(point["fare_usd"])
            point["member_fare_usd"] = _money(point["member_fare_usd"])
            point["casual_fare_usd"] = _money(point["casual_fare_usd"])
            point["energy_kwh_known"] = _decimal(point["energy_kwh_known"])
            point["duration_seconds_average"] = (
                round(point["duration_seconds_total"] / point["trips"], 2)
                if point["trips"] else None
            )
            trends.append({"bucket": label, **point})

        total_trips = sum(point["trips"] for point in bins.values())
        return {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "bucket": bucket,
            "weekly_boundary": "Monday 00:00 local time (UTC-04:00)",
            "summary": {
                "completed_trips": total_trips,
                "duration_seconds_total": total_duration,
                "duration_seconds_average": (
                    round(total_duration / total_trips, 2) if total_trips else None
                ),
                "fare_usd_total": _money(total_fare),
                "fare_usd_average": (
                    _money(total_fare / total_trips) if total_trips else None
                ),
                "fare_usd_by_user_type": {
                    user_type: _money(amount)
                    for user_type, amount in fares_by_user_type.items()
                },
                "energy_kwh_known_total": _decimal(known_energy),
                "energy_unknown_trips": unknown_energy,
                "energy_coverage_percent": (
                    round(100 * (energy_applicable - unknown_energy) / energy_applicable, 2)
                    if energy_applicable else 100.0
                ),
                "duplicate_ride_records": duplicate_rides,
                "conflicting_ride_records": conflicting_rides,
                "warning_trips": warning_trips,
            },
            "trends": trends,
            "time_of_day": [
                {"period": name, "trips": time_of_day[name]}
                for name, _, _ in TIME_PERIODS
            ],
            "station_utilization": station_utilization,
            "status_coverage": {
                "stations_with_observations": sum(
                    row["observed_status_updates"] > 0 for row in station_utilization
                ),
                "observations_are_updates_not_elapsed_time": True,
            },
        }
