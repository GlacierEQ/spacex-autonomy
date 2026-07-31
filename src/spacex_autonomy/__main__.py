from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hybrid_autonomy import Sensors

from .consensus import VehicleEstimate
from .models import TelemetrySample
from .simulation import AutonomySimulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autonomy-sim",
        description="Run one deterministic autonomy simulation step.",
    )
    parser.add_argument("--timestamp", type=float, default=0.0)
    parser.add_argument("--position", type=float, default=0.0)
    parser.add_argument("--velocity", type=float, default=0.0)
    parser.add_argument("--acceleration", type=float, default=0.0)
    parser.add_argument("--telemetry-confidence", type=float, default=0.9)
    parser.add_argument("--imu-confidence", type=float, default=0.9)
    parser.add_argument("--vision-confidence", type=float, default=0.8)
    parser.add_argument("--gps-confidence", type=float, default=0.9)
    parser.add_argument("--link-confidence", type=float, default=0.8)
    parser.add_argument("--target-position", type=float, default=100.0)
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
    print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
