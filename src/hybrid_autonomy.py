#!/usr/bin/env python3
"""Deterministic autonomy-mode selection from bounded sensor confidence inputs.

This module is a simulation policy surface. It does not certify a vehicle,
execute flight controls, or infer sensor confidence from raw telemetry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

WEIGHTS: Final = {
    "imu_conf": 0.30,
    "vision_conf": 0.25,
    "gps_conf": 0.25,
    "link_conf": 0.20,
}


class AutonomyInputError(ValueError):
    """Raised when confidence or policy input is malformed."""


class OperatingMode(StrEnum):
    MANUAL = "MANUAL"
    ASSIST = "ASSIST"
    AUTO = "AUTO"


def _bounded_unit_value(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AutonomyInputError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise AutonomyInputError(f"{name} must be finite and within [0, 1]")
    return numeric


@dataclass(frozen=True, slots=True)
class Sensors:
    imu_conf: float
    vision_conf: float
    gps_conf: float
    link_conf: float

    def validate(self) -> None:
        for name, value in (
            ("imu_conf", self.imu_conf),
            ("vision_conf", self.vision_conf),
            ("gps_conf", self.gps_conf),
            ("link_conf", self.link_conf),
        ):
            _bounded_unit_value(name, value)


@dataclass(frozen=True, slots=True)
class ModePolicy:
    manual_enter: float = 0.45
    manual_exit: float = 0.50
    auto_exit: float = 0.70
    auto_enter: float = 0.75

    def validate(self) -> None:
        manual_enter = _bounded_unit_value("manual_enter", self.manual_enter)
        manual_exit = _bounded_unit_value("manual_exit", self.manual_exit)
        auto_exit = _bounded_unit_value("auto_exit", self.auto_exit)
        auto_enter = _bounded_unit_value("auto_enter", self.auto_enter)
        ordered = 0.0 <= manual_enter <= manual_exit < auto_exit <= auto_enter <= 1.0
        if not ordered:
            raise AutonomyInputError(
                "mode thresholds must satisfy 0 <= manual_enter <= manual_exit "
                "< auto_exit <= auto_enter <= 1"
            )


@dataclass(frozen=True, slots=True)
class ModeDecision:
    mode: OperatingMode
    confidence: float
    previous_mode: OperatingMode
    hysteresis_applied: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "glaciereq.spacex-autonomy.mode-decision.v1",
            "mode": self.mode.value,
            "confidence": round(self.confidence, 6),
            "previous_mode": self.previous_mode.value,
            "hysteresis_applied": self.hysteresis_applied,
        }


def weighted_confidence(sensors: Sensors) -> float:
    """Return the configured weighted confidence without artificial flooring."""

    sensors.validate()
    return sum(getattr(sensors, name) * weight for name, weight in WEIGHTS.items())


def select_mode(
    sensors: Sensors,
    previous: OperatingMode = OperatingMode.ASSIST,
    policy: ModePolicy | None = None,
) -> ModeDecision:
    """Select an operating mode with explicit entry and exit hysteresis."""

    if not isinstance(previous, OperatingMode):
        raise AutonomyInputError("previous mode must be an OperatingMode")
    active_policy = policy or ModePolicy()
    active_policy.validate()
    confidence = weighted_confidence(sensors)

    if confidence < active_policy.manual_enter:
        candidate = OperatingMode.MANUAL
    elif confidence >= active_policy.auto_enter:
        candidate = OperatingMode.AUTO
    else:
        candidate = OperatingMode.ASSIST

    selected = candidate
    if previous is OperatingMode.AUTO and confidence >= active_policy.auto_exit:
        selected = OperatingMode.AUTO
    elif previous is OperatingMode.MANUAL and confidence < active_policy.manual_exit:
        selected = OperatingMode.MANUAL

    return ModeDecision(
        mode=selected,
        confidence=confidence,
        previous_mode=previous,
        hysteresis_applied=selected is not candidate,
    )


def mode(sensors: Sensors, prev: str = "ASSIST") -> dict[str, object]:
    """Compatibility wrapper returning the stable JSON-ready decision schema."""

    try:
        previous = OperatingMode(prev)
    except ValueError as exc:
        raise AutonomyInputError(f"unknown previous mode: {prev!r}") from exc
    return select_mode(sensors, previous).to_dict()


if __name__ == "__main__":
    print(mode(Sensors(0.9, 0.85, 0.8, 0.9)))
    print(mode(Sensors(0.3, 0.2, 0.4, 0.5), prev="AUTO"))
