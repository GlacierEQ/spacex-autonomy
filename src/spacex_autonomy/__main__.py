from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence

from hybrid_autonomy import Sensors

from .consensus import VehicleEstimate
from .models import TelemetrySample
from .simulation import AutonomySimulation


def finite_float(value: str) -> float:
    """Parse one finite numeric CLI value."""

    try:
        numeric = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a real number") from exc
    if not math.isfinite(numeric):
        raise argparse.ArgumentTypeError("value must be finite")
    return numeric


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autonomy-sim",
        description="Run one deterministic autonomy simulation step.",
    )
    parser.add_argument("--timestamp", type=finite_float, default=0.0)
    parser.add_argument("--position", type=finite_float, default=0.0)
    parser.add_argument("--velocity", type=finite_float, default=0.0)
    parser.add_argument("--acceleration", type=finite_float, default=0.0)
    parser.add_argument("--telemetry-confidence", type=finite_float, default=0.9)
    parser.add_argument("--imu-confidence", type=finite_float, default=0.9)
    parser.add_argument("--vision-confidence", type=finite_float, default=0.8)
    parser.add_argument("--gps-confidence", type=finite_float, default=0.9)
    parser.add_argument("--link-confidence", type=finite_float, default=0.8)
    parser.add_argument("--target-position", type=finite_float, default=100.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    namespace = build_parser().parse_args(argv)
    simulation = AutonomySimulation()
    snapshot = simulation.step(
        telemetry=TelemetrySample(
            timestamp_s=namespace.timestamp,
            position_m=namespace.position,
            velocity_mps=namespace.velocity,
            acceleration_mps2=namespace.acceleration,
            confidence=namespace.telemetry_confidence,
        ),
        sensor_confidence=Sensors(
            namespace.imu_confidence,
            namespace.vision_confidence,
            namespace.gps_confidence,
            namespace.link_confidence,
        ),
        target_position_m=namespace.target_position,
        peer_estimates=[
            VehicleEstimate("local", namespace.position, namespace.velocity, 0.9, 1.0)
        ],
    )
    print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
