from __future__ import annotations

from hybrid_autonomy import OperatingMode, Sensors, select_mode

from .consensus import VehicleEstimate, fuse_estimates
from .control import PositionController
from .estimation import AlphaBetaEstimator
from .models import SimulationSnapshot, TelemetrySample

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

    def step(
        self,
        *,
        telemetry: TelemetrySample,
        sensor_confidence: Sensors,
        target_position_m: float,
        peer_estimates: list[VehicleEstimate] | None = None,
    ) -> SimulationSnapshot:
        mode_decision = select_mode(sensor_confidence, self._previous_mode)
        self._previous_mode = mode_decision.mode
        estimated_state = self.estimator.update(telemetry)
        control = self.controller.command(
            estimated_state,
            target_position_m=target_position_m,
            enabled=mode_decision.mode is not OperatingMode.MANUAL,
        )
        consensus = fuse_estimates(peer_estimates or [])

        return SimulationSnapshot(
            schema=SNAPSHOT_SCHEMA,
            mode=mode_decision.mode.value,
            confidence=mode_decision.confidence,
            estimated_state=estimated_state,
            control=control,
            consensus=consensus,
        )
