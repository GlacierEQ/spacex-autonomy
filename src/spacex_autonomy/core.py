"""Orbital Mechanics & Conjunction Assessment — Core Module"""

import math
from dataclasses import dataclass

MU_EARTH = 3.986004418e14  # m^3/s^2

@dataclass(frozen=True)
class KeplerianState:
    """Six-element Keplerian orbital state vector."""
    semi_major_axis: float    # meters
    eccentricity: float       # dimensionless [0, 1)
    inclination: float        # radians
    raan: float               # right ascension of ascending node (rad)
    arg_periapsis: float      # argument of periapsis (rad)
    true_anomaly: float       # radians

    @property
    def orbital_period(self) -> float:
        """Kepler's third law: T = 2π√(a³/μ)."""
        return 2.0 * math.pi * math.sqrt(self.semi_major_axis ** 3 / MU_EARTH)

    @property
    def apoapsis(self) -> float:
        return self.semi_major_axis * (1.0 + self.eccentricity)

    @property
    def periapsis(self) -> float:
        return self.semi_major_axis * (1.0 - self.eccentricity)

    @property
    def specific_energy(self) -> float:
        """Vis-viva specific orbital energy: ε = -μ/(2a)."""
        return -MU_EARTH / (2.0 * self.semi_major_axis)

    @property
    def velocity_at_periapsis(self) -> float:
        """v = √(μ(2/r - 1/a)) at periapsis."""
        r = self.periapsis
        return math.sqrt(MU_EARTH * (2.0 / r - 1.0 / self.semi_major_axis))

    def mean_motion(self) -> float:
        """n = √(μ/a³) rad/s."""
        return math.sqrt(MU_EARTH / self.semi_major_axis ** 3)


class ConjunctionScreener:
    """Screens two orbits for potential conjunction events."""

    def __init__(self, threshold_km: float = 5.0):
        self.threshold_m = threshold_km * 1000.0

    def miss_distance_estimate(self, state_a: KeplerianState, state_b: KeplerianState) -> float:
        """Rough coplanar miss distance (meters) between two orbits at closest approach."""
        r_a = state_a.semi_major_axis * (1.0 - state_a.eccentricity ** 2) / (
            1.0 + state_a.eccentricity * math.cos(state_a.true_anomaly)
        )
        r_b = state_b.semi_major_axis * (1.0 - state_b.eccentricity ** 2) / (
            1.0 + state_b.eccentricity * math.cos(state_b.true_anomaly)
        )
        return abs(r_a - r_b)

    def is_conjunction(self, state_a: KeplerianState, state_b: KeplerianState) -> bool:
        return self.miss_distance_estimate(state_a, state_b) < self.threshold_m

