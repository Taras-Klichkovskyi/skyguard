"""Правила якості даних для краудсорс-звітів (SG-2).

DQ-1 Geofence  — репортер не далі ніж за 100 м від входу в укриття.
DQ-2 Freshness — спостереження зроблено не раніше ніж 30 хв тому.
DQ-3 Quorum    — сума ваг незалежних звітів з однаковим статусом за 15 хв ≥ 3.

Кожне правило — окремий клас зі спільним інтерфейсом, тож нові перевірки
додаються до конвеєра без зміни коду, що його викликає.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.models.enums import RejectionCode


@dataclass(frozen=True)
class Violation:
    rule: str
    code: RejectionCode
    message: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    """Те, що відомо про звіт на момент перевірки."""

    distance_m: float
    observed_at: datetime
    received_at: datetime


class DataQualityRule:
    rule = ""

    def check(self, evidence: Evidence) -> Violation | None:
        raise NotImplementedError


class HaversineRule(DataQualityRule):
    rule = "DQ-1"

    def check(self, evidence: Evidence) -> Violation | None:
        limit = get_settings().dq_max_distance_m
        if evidence.distance_m <= limit:
            return None
        distance = round(evidence.distance_m)
        return Violation(
            self.rule,
            RejectionCode.GEOLOCATION_OUT_OF_BOUNDS,
            f"Ви за {distance} м від укриття. Звіт приймається в межах {limit} м: "
            "підійдіть ближче до входу.",
            {"distance_m": round(evidence.distance_m, 1), "max_distance_m": limit},
        )


class FreshnessRule(DataQualityRule):
    rule = "DQ-2"

    def check(self, evidence: Evidence) -> Violation | None:
        limit = get_settings().dq_max_age_min
        age = evidence.received_at - evidence.observed_at
        if age <= timedelta(minutes=limit):
            return None
        return Violation(
            self.rule,
            RejectionCode.STALE_DATA,
            f"Спостереження застаріло: минуло {int(age.total_seconds() // 60)} хв, "
            f"а звіт приймається не пізніше ніж через {limit} хв.",
            {"age_min": int(age.total_seconds() // 60), "max_age_min": limit},
        )


# Порядок має значення: спершу дешевша перевірка часу, потім геоприв'язка
PIPELINE: tuple[DataQualityRule, ...] = (FreshnessRule(), HaversineRule())


def first_violation(evidence: Evidence) -> Violation | None:
    for rule in PIPELINE:
        violation = rule.check(evidence)
        if violation is not None:
            return violation
    return None


@dataclass(frozen=True)
class Quorum:
    """Стан кворуму DQ-3 для одного статусу одного укриття."""

    collected: int
    required: int
    window_min: int

    @property
    def reached(self) -> bool:
        return self.collected >= self.required


class QuorumRule:
    rule = "DQ-3"

    def evaluate(self, weights: list[int]) -> Quorum:
        settings = get_settings()
        return Quorum(sum(weights), settings.dq_quorum_weight, settings.dq_quorum_window_min)
