from __future__ import annotations

import math
from dataclasses import dataclass

from .models import EstimatedState, SimulationInputError, TelemetrySample


def _real_value(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationInputError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise SimulationInputError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class EstimatorPolicy:
    alpha: float = 0.65
    beta: float = 0.20
    minimum_measurement_confidence: float = 0.25
    maximum_innovation_m: float = 500.0

    def validate(self) -> None:
        alpha = _real_value("alpha", self.alpha)
        beta = _real_value("beta", self.beta)
        minimum_confidence = _real_value(
            "minimum measurement confidence",
            self.minimum_measurement_confidence,
        )
        maximum_innovation = _real_value("maximum innovation", self.maximum_innovation_m)
        if not 0.0 < alpha <= 1.0:
            raise SimulationInputError("alpha must be within (0, 1]")
        if not 0.0 <= beta <= 1.0:
            raise SimulationInputError("beta must be within [0, 1]")
        if not 0.0 <= minimum_confidence <= 1.0:
            raise SimulationInputError("minimum measurement confidence must be within [0, 1]")
        if maximum_innovation <= 0.0:
            raise SimulationInputError("maximum innovation must be positive")


class AlphaBetaEstimator:
    """Small deterministic position/velocity estimator for simulation evidence."""

    def __init__(self, policy: EstimatorPolicy | None = None) -> None:
        active_policy = policy or EstimatorPolicy()
        active_policy.validate()
        self.policy = active_policy
        self._initialized = False
        self._timestamp_s = 0.0
        self._position_m = 0.0
        self._velocity_mps = 0.0

    def update(self, sample: TelemetrySample) -> EstimatedState:
        sample.validate()
        if not self._initialized:
            self._initialized = True
            self._timestamp_s = sample.timestamp_s
            self._position_m = sample.position_m
            self._velocity_mps = sample.velocity_mps
            return EstimatedState(
                timestamp_s=sample.timestamp_s,
                position_m=self._position_m,
                velocity_mps=self._velocity_mps,
                innovation_m=0.0,
                measurement_used=True,
            )

        dt = sample.timestamp_s - self._timestamp_s
        if dt <= 0.0:
            raise SimulationInputError("telemetry timestamps must increase monotonically")

        predicted_position = (
            self._position_m
            + self._velocity_mps * dt
            + 0.5 * sample.acceleration_mps2 * dt * dt
        )
        predicted_velocity = self._velocity_mps + sample.acceleration_mps2 * dt
        innovation = sample.position_m - predicted_position
        measurement_used = (
            sample.confidence >= self.policy.minimum_measurement_confidence
            and abs(innovation) <= self.policy.maximum_innovation_m
        )

        if measurement_used:
            confidence = sample.confidence
            position_gain = self.policy.alpha * confidence
            velocity_gain = self.policy.beta * confidence
            self._position_m = predicted_position + position_gain * innovation
            self._velocity_mps = (
                predicted_velocity + velocity_gain * innovation / dt
            )
        else:
            self._position_m = predicted_position
            self._velocity_mps = predicted_velocity

        self._timestamp_s = sample.timestamp_s
        return EstimatedState(
            timestamp_s=sample.timestamp_s,
            position_m=self._position_m,
            velocity_mps=self._velocity_mps,
            innovation_m=innovation,
            measurement_used=measurement_used,
        )
