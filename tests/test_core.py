from __future__ import annotations

import json

import pytest

from spacex_autonomy import (
    AlphaBetaEstimator,
    AutonomySimulation,
    ControllerPolicy,
    EstimatorPolicy,
    PositionController,
    Sensors,
    SimulationInputError,
    TelemetrySample,
    VehicleEstimate,
    fuse_estimates,
)


def sample(
    timestamp: float,
    position: float,
    *,
    velocity: float = 0.0,
    acceleration: float = 0.0,
    confidence: float = 1.0,
) -> TelemetrySample:
    return TelemetrySample(timestamp, position, velocity, acceleration, confidence)


def test_estimator_initializes_from_first_sample() -> None:
    estimator = AlphaBetaEstimator()
    state = estimator.update(sample(1.0, 10.0, velocity=2.0))
    assert state.position_m == 10.0
    assert state.velocity_mps == 2.0
    assert state.measurement_used is True


def test_estimator_predicts_and_corrects_deterministically() -> None:
    estimator = AlphaBetaEstimator(EstimatorPolicy(alpha=0.5, beta=0.25))
    estimator.update(sample(0.0, 0.0, velocity=10.0))
    state = estimator.update(sample(1.0, 12.0, velocity=10.0))
    assert state.innovation_m == pytest.approx(2.0)
    assert state.position_m == pytest.approx(11.0)
    assert state.velocity_mps == pytest.approx(10.5)


def test_low_confidence_measurement_uses_prediction_only() -> None:
    estimator = AlphaBetaEstimator()
    estimator.update(sample(0.0, 0.0, velocity=5.0))
    state = estimator.update(sample(2.0, 500.0, velocity=5.0, confidence=0.1))
    assert state.position_m == pytest.approx(10.0)
    assert state.measurement_used is False


def test_large_innovation_is_rejected() -> None:
    estimator = AlphaBetaEstimator(EstimatorPolicy(maximum_innovation_m=20.0))
    estimator.update(sample(0.0, 0.0))
    state = estimator.update(sample(1.0, 100.0))
    assert state.position_m == 0.0
    assert state.measurement_used is False


def test_estimator_requires_monotonic_time() -> None:
    estimator = AlphaBetaEstimator()
    estimator.update(sample(1.0, 0.0))
    with pytest.raises(SimulationInputError, match="increase monotonically"):
        estimator.update(sample(1.0, 1.0))


def test_controller_is_bounded_and_can_be_disabled() -> None:
    estimator = AlphaBetaEstimator()
    state = estimator.update(sample(0.0, 0.0, velocity=50.0))
    controller = PositionController(
        ControllerPolicy(proportional_gain=1.0, derivative_gain=1.0, command_limit=0.5)
    )
    enabled = controller.command(state, target_position_m=1_000.0, enabled=True)
    disabled = controller.command(state, target_position_m=1_000.0, enabled=False)
    assert enabled.normalized_command == 0.5
    assert disabled.normalized_command == 0.0
    assert disabled.enabled is False


def test_consensus_weights_confidence_and_uncertainty() -> None:
    consensus = fuse_estimates(
        [
            VehicleEstimate("a", 0.0, 0.0, confidence=1.0, uncertainty=1.0),
            VehicleEstimate("b", 10.0, 4.0, confidence=0.5, uncertainty=2.0),
        ]
    )
    assert consensus is not None
    assert consensus.position_m == pytest.approx(2.0)
    assert consensus.velocity_mps == pytest.approx(0.8)
    assert consensus.participants == 2


def test_consensus_rejects_duplicate_vehicle_identity() -> None:
    with pytest.raises(SimulationInputError, match="duplicate vehicle_id"):
        fuse_estimates(
            [
                VehicleEstimate("a", 0.0, 0.0, 1.0, 1.0),
                VehicleEstimate("a", 1.0, 0.0, 1.0, 1.0),
            ]
        )


def test_zero_aggregate_confidence_cannot_form_consensus() -> None:
    with pytest.raises(SimulationInputError, match="positive aggregate confidence"):
        fuse_estimates([VehicleEstimate("a", 0.0, 0.0, 0.0, 1.0)])


def test_simulation_integrates_mode_estimation_control_and_consensus() -> None:
    simulation = AutonomySimulation()
    snapshot = simulation.step(
        telemetry=sample(0.0, 5.0, velocity=1.0),
        sensor_confidence=Sensors(0.9, 0.9, 0.9, 0.9),
        target_position_m=100.0,
        peer_estimates=[VehicleEstimate("peer", 6.0, 1.0, 0.9, 1.0)],
    )
    payload = snapshot.to_dict()
    assert payload["schema"] == "glaciereq.spacex-autonomy.simulation-snapshot.v1"
    assert payload["mode"] == "AUTO"
    assert payload["control"]["enabled"] is True
    assert payload["consensus"]["participants"] == 1
    json.dumps(payload, sort_keys=True)


def test_manual_mode_disables_control_output() -> None:
    simulation = AutonomySimulation()
    snapshot = simulation.step(
        telemetry=sample(0.0, 0.0),
        sensor_confidence=Sensors(0.1, 0.1, 0.1, 0.1),
        target_position_m=100.0,
    )
    assert snapshot.mode == "MANUAL"
    assert snapshot.control.enabled is False
    assert snapshot.control.normalized_command == 0.0
