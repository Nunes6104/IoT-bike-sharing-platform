"""Isolated fare and straight-line energy calculations."""

import math
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any


CENT = Decimal("0.01")
WH_PER_KM = Decimal("15")
EARTH_RADIUS_KM = 6371.0088


def estimate_fare_usd(
    duration_seconds: int,
    member_casual: str,
    rideable_type: str,
) -> Decimal:
    """Estimate fare; round overage minutes up and the final amount half-up to cents."""
    if not isinstance(duration_seconds, int) or isinstance(duration_seconds, bool):
        raise ValueError("duration_seconds must be a non-negative integer")
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be a non-negative integer")
    if member_casual not in ("member", "casual"):
        raise ValueError("member_casual must be member or casual")
    if rideable_type not in ("classic_bike", "electric_bike"):
        raise ValueError("rideable_type must be classic_bike or electric_bike")

    duration = Decimal(duration_seconds)
    if member_casual == "member":
        included_seconds = Decimal(45 * 60)
        overage_rate = Decimal("0.20")
        base = Decimal("0")
        electric_rate = Decimal("0.25")
    else:
        included_seconds = Decimal(30 * 60)
        overage_rate = Decimal("0.30")
        base = Decimal("4.50")
        electric_rate = Decimal("0.35")

    overage_seconds = max(Decimal(0), duration - included_seconds)
    overage_minutes = (overage_seconds / Decimal(60)).to_integral_value(
        rounding=ROUND_CEILING
    )
    fare = base + overage_minutes * overage_rate
    if rideable_type == "electric_bike":
        fare += duration / Decimal(60) * electric_rate
    return fare.quantize(CENT, rounding=ROUND_HALF_UP)


def straight_line_distance_km(event: dict[str, Any]) -> float | None:
    """Return Haversine distance, or None when either trip coordinate is absent."""
    coordinate_names = ("start_lat", "start_lng", "end_lat", "end_lng")
    coordinates = [event.get(name) for name in coordinate_names]
    if any(value is None for value in coordinates):
        return None
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        for value in coordinates
    ):
        return None
    start_lat, start_lng, end_lat, end_lng = map(math.radians, coordinates)
    delta_lat = end_lat - start_lat
    delta_lng = end_lng - start_lng
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(start_lat) * math.cos(end_lat) * math.sin(delta_lng / 2) ** 2
    )
    central_angle = 2 * math.asin(math.sqrt(min(1.0, haversine)))
    return EARTH_RADIUS_KM * central_angle


def estimate_energy_kwh(event: dict[str, Any]) -> Decimal | None:
    """Estimate e-bike energy in kWh; preserve unknown distance as None."""
    rideable_type = event.get("rideable_type")
    if rideable_type == "classic_bike":
        return Decimal("0")
    if rideable_type != "electric_bike":
        raise ValueError("rideable_type must be classic_bike or electric_bike")
    distance_km = straight_line_distance_km(event)
    if distance_km is None:
        return None
    energy_wh = Decimal(str(distance_km)) * WH_PER_KM
    return energy_wh / Decimal(1000)
