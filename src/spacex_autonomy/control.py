from __future__ import annotations

import math
from dataclasses import dataclass

from .models import ControlCommand, EstimatedState, SimulationInputError


def _real_value(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationInputError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise SimulationInputError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class ControllerPolicy:
    proportional_gain: float = 0.01
    derivative_gain: float = 0.002
    command_limit: float = 1.0

    def validate(self) -> None:
        proportional_gain = _real_value("proportional gain", self.proportional_gain)
        derivative_gain = _real_value("derivative gain", self.derivative_gain)
        command_limit = _real_value("command limit", self.command_limit)
        if proportional_gain < 0.0:
            raise SimulationInputError("proportional gain cannot be negative")
        if derivative_gain < 0.0:
            raise SimulationInputError("derivative gain cannot be negative")
        if command_limit <= 0.0:
            raise SimulationInputError("command limit must be positive")


class PositionController:
    """Deterministic bounded controller for one-dimensional simulation."""

    def __init__(self, policy: ControllerPolicy | None = None) -> None:
        active_policy = policy or ControllerPolicy()
        active_policy.validate()
        self.policy = active_policy

    def command(
        self,
        state: EstimatedState,
        *,
        target_position_m: float,
        enabled: bool,
    ) -> ControlCommand:
        target = _real_value("target position", target_position_m)
        error = target - state.position_m
        if not enabled:
            normalized = 0.0
        else:
            raw = (
                self.policy.proportional_gain * error
                - self.policy.derivative_gain * state.velocity_mps
            )
            normalized = max(-self.policy.command_limit, min(self.policy.command_limit, raw))

        return ControlCommand(
            target_position_m=target,
            position_error_m=error,
            normalized_command=normalized,
            enabled=enabled,
        )
