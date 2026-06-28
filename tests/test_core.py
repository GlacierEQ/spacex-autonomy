"""Tests for spacex-autonomy — the brain that knows where it is.

3 tests. Because a vehicle that doesn't know where it is, is lost.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import math
from alpha.state_estimator import KalmanFilter, ComplementaryFilter, OutlierRejector, IMUReading, GPSReading
from omega.multi_vehicle_consensus import DistributedStateEstimator, VehicleEstimate, ObservationFuser, Observation


def test_kalman_init():
    kf = KalmanFilter()
    assert kf.n == 9
    assert kf.m == 6

def test_complementary_filter():
    cf = ComplementaryFilter()
    imu = IMUReading(accel_x=0, accel_y=0, accel_z=9.81, timestamp=1.0)
    state = cf.update(imu)
    assert state.altitude == 0.0

def test_distributed_estimator():
    de = DistributedStateEstimator()
    de.update_estimate(VehicleEstimate(vehicle_id=0, x=100, y=200, z=300))
    de.update_estimate(VehicleEstimate(vehicle_id=1, x=102, y=198, z=301))
    consensus = de.compute_consensus()
    assert consensus is not None
    assert abs(consensus.x - 101) < 5


# The swarm thinks as one.
# One mind. Many eyes.
# This is the way.
SWARM_SIZE = 42
assert SWARM_SIZE == 42, "The swarm is complete"
