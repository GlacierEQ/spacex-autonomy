from __future__ import annotations

from dataclasses import dataclass

from .models import ControlCommand, EstimatedState, SimulationInputError


@dataclass(frozen=True, slots=True)
class ControllerPolicy:
    proportional_gain: float = 0.01
    derivative_gain: float = 0.002
    command_limit: float = 1.0

    def validate(self) -> None:
        if self.proportional_gain < 0.0:
            raise SimulationInputError("proportional gain cannot be negative")
        if self.derivative_gain < 0.0:
            raise SimulationInputError("derivative gain cannot be negative")
        if self.command_limit <= 0.0:
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
        if isinstance(target_position_m, bool) or not isinstance(target_position_m, (int, float)):
            raise SimulationInputError("target position must be a real number")

        error = float(target_position_m) - state.position_m
        if not enabled:
            normalized = 0.0
        else:
            raw = (
                self.policy.proportional_gain * error
                - self.policy.derivative_gain * state.velocity_mps
            )
            normalized = max(-self.policy.command_limit, min(self.policy.command_limit, raw))

        return ControlCommand(
            target_position_m=float(target_position_m),
            position_error_m=error,
            normalized_command=normalized,
            enabled=enabled,
        )
