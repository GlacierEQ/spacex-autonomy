from __future__ import annotations

import math

from hybrid_autonomy import OperatingMode, Sensors, select_mode

from .consensus import VehicleEstimate, fuse_estimates
from .control import PositionController
from .estimation import AlphaBetaEstimator
from .models import SimulationInputError, SimulationSnapshot, TelemetrySample

SNAPSHOT_SCHEMA = "glaciereq.spacex-autonomy.simulation-snapshot.v1"


class AutonomySimulation:
    """Deterministic, one-dimensional autonomy integration simulation.

    The simulation combines independently testable mode selection, state
    estimation, bounded control, and optional weighted consensus. It does not
    execute actuators or represent flight-certified guidance software.
    """

    def __init__(
        self,
        *,
        estimator: AlphaBetaEstimator | None = None,
        controller: PositionController | None = None,
    ) -> None:
        self.estimator = estimator or AlphaBetaEstimator()
        self.controller = controller or PositionController()
        self._previous_mode = OperatingMode.ASSIST

    @property
    def previous_mode(self) -> OperatingMode:
        """Return the last successfully committed mode."""

        return self._previous_mode

    def step(
        self,
        *,
        telemetry: TelemetrySample,
        sensor_confidence: Sensors,
        target_position_m: float,
        peer_estimates: list[VehicleEstimate] | None = None,
    ) -> SimulationSnapshot:
        """Run one atomic simulation step.

        All failure-prone inputs are validated before the estimator or mode
        history is mutated. A failed call therefore cannot advance state that
        belongs to a snapshot the caller never received.
        """

        telemetry.validate()
        mode_decision = select_mode(sensor_confidence, self._previous_mode)
        if isinstance(target_position_m, bool) or not isinstance(target_position_m, (int, float)):
            raise SimulationInputError("target position must be a real number")
        if not math.isfinite(target_position_m):
            raise SimulationInputError("target position must be finite")
        consensus = fuse_estimates(peer_estimates or [])

        estimated_state = self.estimator.update(telemetry)
        control = self.controller.command(
            estimated_state,
            target_position_m=target_position_m,
            enabled=mode_decision.mode is not OperatingMode.MANUAL,
        )
        snapshot = SimulationSnapshot(
            schema=SNAPSHOT_SCHEMA,
            mode=mode_decision.mode.value,
            confidence=mode_decision.confidence,
            estimated_state=estimated_state,
            control=control,
            consensus=consensus,
        )
        self._previous_mode = mode_decision.mode
        return snapshot
