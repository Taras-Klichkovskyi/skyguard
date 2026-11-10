"""Геообчислення. Формула гаверсинуса — та сама, що у правилі DQ-1 (SG-2)."""

from math import atan2, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000
WALKING_SPEED_M_PER_MIN = 80  # ≈ 4,8 км/год


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Відстань між двома точками WGS84 у метрах."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))


def walk_minutes(distance_m: float) -> int:
    return max(1, round(distance_m / WALKING_SPEED_M_PER_MIN))
