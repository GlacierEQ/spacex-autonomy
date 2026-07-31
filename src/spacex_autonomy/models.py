from __future__ import annotations

import math
from dataclasses import dataclass


class SimulationInputError(ValueError):
    """Raised when simulation input is malformed or physically nonsensical."""


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationInputError(f"{name} must be a real number")
    if not math.isfinite(value):
        raise SimulationInputError(f"{name} must be finite")
    return float(value)


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    timestamp_s: float
    position_m: float
    velocity_mps: float
    acceleration_mps2: float
    confidence: float

    def validate(self) -> None:
        _finite("timestamp_s", self.timestamp_s)
        _finite("position_m", self.position_m)
        _finite("velocity_mps", self.velocity_mps)
        _finite("acceleration_mps2", self.acceleration_mps2)
        confidence = _finite("confidence", self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise SimulationInputError("confidence must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class EstimatedState:
    timestamp_s: float
    position_m: float
    velocity_mps: float
    innovation_m: float
    measurement_used: bool


@dataclass(frozen=True, slots=True)
class ControlCommand:
    target_position_m: float
    position_error_m: float
    normalized_command: float
    enabled: bool


@dataclass(frozen=True, slots=True)
class ConsensusEstimate:
    position_m: float
    velocity_mps: float
    uncertainty: float
    participants: int


@dataclass(frozen=True, slots=True)
class SimulationSnapshot:
    schema: str
    mode: str
    confidence: float
    estimated_state: EstimatedState
    control: ControlCommand
    consensus: ConsensusEstimate | None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "mode": self.mode,
            "confidence": round(self.confidence, 6),
            "estimated_state": {
                "timestamp_s": self.estimated_state.timestamp_s,
                "position_m": self.estimated_state.position_m,
                "velocity_mps": self.estimated_state.velocity_mps,
                "innovation_m": self.estimated_state.innovation_m,
                "measurement_used": self.estimated_state.measurement_used,
            },
            "control": {
                "target_position_m": self.control.target_position_m,
                "position_error_m": self.control.position_error_m,
                "normalized_command": self.control.normalized_command,
                "enabled": self.control.enabled,
            },
            "consensus": (
                {
                    "position_m": self.consensus.position_m,
                    "velocity_mps": self.consensus.velocity_mps,
                    "uncertainty": self.consensus.uncertainty,
                    "participants": self.consensus.participants,
                }
                if self.consensus
                else None
            ),
        }
