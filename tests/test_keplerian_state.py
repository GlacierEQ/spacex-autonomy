"""Auto-generated tests for Orbital Mechanics & Conjunction Assessment."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import math
from spacex_autonomy.core import KeplerianState, ConjunctionScreener, MU_EARTH

def test_orbital_period_iss():
    """ISS orbit: ~408 km altitude, period ~92.7 min."""
    alt_km = 408.0
    a = (6371.0 + alt_km) * 1000.0
    state = KeplerianState(a, 0.0005, math.radians(51.6), 0.0, 0.0, 0.0)
    period_min = state.orbital_period / 60.0
    assert 90.0 < period_min < 95.0, f"ISS period {{period_min:.1f}} min out of range"

def test_circular_orbit_apoapsis_equals_periapsis():
    a = 7_000_000.0
    state = KeplerianState(a, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert abs(state.apoapsis - state.periapsis) < 1.0

def test_specific_energy_negative_for_bound_orbit():
    state = KeplerianState(7_000_000.0, 0.01, 0.0, 0.0, 0.0, 0.0)
    assert state.specific_energy < 0.0

def test_conjunction_screener_close_orbits():
    s1 = KeplerianState(7_000_000.0, 0.001, 0.0, 0.0, 0.0, 0.0)
    s2 = KeplerianState(7_003_000.0, 0.001, 0.0, 0.0, 0.0, 0.0)
    screener = ConjunctionScreener(threshold_km=5.0)
    assert screener.is_conjunction(s1, s2)

def test_conjunction_screener_far_orbits():
    s1 = KeplerianState(7_000_000.0, 0.001, 0.0, 0.0, 0.0, 0.0)
    s2 = KeplerianState(42_164_000.0, 0.001, 0.0, 0.0, 0.0, 0.0)  # GEO
    screener = ConjunctionScreener(threshold_km=5.0)
    assert not screener.is_conjunction(s1, s2)

def test_mean_motion_positive():
    state = KeplerianState(7_000_000.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert state.mean_motion() > 0.0

def test_velocity_at_periapsis():
    state = KeplerianState(7_000_000.0, 0.1, 0.0, 0.0, 0.0, 0.0)
    v = state.velocity_at_periapsis
    assert 7000.0 < v < 8500.0, f"Periapsis velocity {{v:.0f}} m/s out of range"

