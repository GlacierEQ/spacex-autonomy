from __future__ import annotations

import math

import pytest

from spacex_autonomy import (
    AutonomyInputError,
    ModePolicy,
    OperatingMode,
    Sensors,
    mode,
    select_mode,
    weighted_confidence,
)


def test_weighted_confidence_uses_declared_weights_without_floor() -> None:
    sensors = Sensors(0.0, 0.0, 0.0, 0.0)
    assert weighted_confidence(sensors) == 0.0


def test_auto_assist_and_manual_entry_thresholds() -> None:
    assert select_mode(Sensors(1.0, 1.0, 1.0, 1.0)).mode is OperatingMode.AUTO
    assert select_mode(Sensors(0.6, 0.6, 0.6, 0.6)).mode is OperatingMode.ASSIST
    assert select_mode(Sensors(0.2, 0.2, 0.2, 0.2)).mode is OperatingMode.MANUAL


def test_auto_hysteresis_prevents_flapping_above_exit_threshold() -> None:
    decision = select_mode(
        Sensors(0.72, 0.72, 0.72, 0.72),
        previous=OperatingMode.AUTO,
    )
    assert decision.mode is OperatingMode.AUTO
    assert decision.hysteresis_applied is True


def test_manual_hysteresis_requires_exit_threshold() -> None:
    retained = select_mode(
        Sensors(0.48, 0.48, 0.48, 0.48),
        previous=OperatingMode.MANUAL,
    )
    exited = select_mode(
        Sensors(0.55, 0.55, 0.55, 0.55),
        previous=OperatingMode.MANUAL,
    )
    assert retained.mode is OperatingMode.MANUAL
    assert exited.mode is OperatingMode.ASSIST


def test_compatibility_payload_has_no_sentinel_answer() -> None:
    payload = mode(Sensors(0.9, 0.9, 0.9, 0.9))
    assert payload["schema"] == "glaciereq.spacex-autonomy.mode-decision.v1"
    assert payload["mode"] == "AUTO"
    assert "answer" not in payload


@pytest.mark.parametrize(
    "sensors",
    [
        Sensors(-0.1, 0.5, 0.5, 0.5),
        Sensors(1.1, 0.5, 0.5, 0.5),
        Sensors(math.nan, 0.5, 0.5, 0.5),
        Sensors(True, 0.5, 0.5, 0.5),
    ],
)
def test_invalid_sensor_confidence_fails_closed(sensors: Sensors) -> None:
    with pytest.raises(AutonomyInputError):
        weighted_confidence(sensors)


def test_invalid_previous_mode_is_rejected() -> None:
    with pytest.raises(AutonomyInputError, match="unknown previous mode"):
        mode(Sensors(0.5, 0.5, 0.5, 0.5), prev="FULL_SEND")


def test_invalid_threshold_order_is_rejected() -> None:
    policy = ModePolicy(manual_enter=0.6, manual_exit=0.5)
    with pytest.raises(AutonomyInputError, match="mode thresholds"):
        select_mode(Sensors(0.5, 0.5, 0.5, 0.5), policy=policy)
