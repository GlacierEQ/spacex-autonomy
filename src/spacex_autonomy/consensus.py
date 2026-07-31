from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .models import ConsensusEstimate, SimulationInputError

MIN_UNCERTAINTY: Final = 1e-6


@dataclass(frozen=True, slots=True)
class VehicleEstimate:
    vehicle_id: str
    position_m: float
    velocity_mps: float
    confidence: float
    uncertainty: float

    def validate(self) -> None:
        if not self.vehicle_id.strip():
            raise SimulationInputError("vehicle_id must be non-empty")
        for name, value in (
            ("position_m", self.position_m),
            ("velocity_mps", self.velocity_mps),
            ("confidence", self.confidence),
            ("uncertainty", self.uncertainty),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SimulationInputError(f"{name} must be a real number")
            if not math.isfinite(value):
                raise SimulationInputError(f"{name} must be finite")
        if not 0.0 <= self.confidence <= 1.0:
            raise SimulationInputError("confidence must be within [0, 1]")
        if self.uncertainty <= 0.0:
            raise SimulationInputError("uncertainty must be positive")


def fuse_estimates(estimates: list[VehicleEstimate]) -> ConsensusEstimate | None:
    """Fuse unique vehicle estimates by confidence divided by uncertainty.

    This is a deterministic weighted average, not Byzantine fault tolerance.
    """

    if not estimates:
        return None

    seen: set[str] = set()
    total_weight = 0.0
    weighted_position = 0.0
    weighted_velocity = 0.0

    for estimate in estimates:
        estimate.validate()
        if estimate.vehicle_id in seen:
            raise SimulationInputError(f"duplicate vehicle_id: {estimate.vehicle_id}")
        seen.add(estimate.vehicle_id)
        weight = estimate.confidence / max(estimate.uncertainty, MIN_UNCERTAINTY)
        total_weight += weight
        weighted_position += estimate.position_m * weight
        weighted_velocity += estimate.velocity_mps * weight

    if total_weight <= 0.0:
        raise SimulationInputError("consensus requires positive aggregate confidence")

    return ConsensusEstimate(
        position_m=weighted_position / total_weight,
        velocity_mps=weighted_velocity / total_weight,
        uncertainty=1.0 / total_weight,
        participants=len(estimates),
    )
