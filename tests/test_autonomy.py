"""Autonomy tests — Kalman filter, complementary filter, flight controller."""

import math
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from alpha.state_estimator import (
    KalmanFilter, ComplementaryFilter, OutlierRejector,
    IMUReading, GPSReading, StateVector,
)
from omega.flight_controller import (
    FlightController, PIDController, PIDGains, AttitudeController,
    TrajectoryTracker, FaultManager, ControlMode, FaultType,
)


def test_kalman_predict():
    kf = KalmanFilter()
    kf.x[2] = 1000.0
    kf.predict(0.1)
    assert kf.x[2] == 1000.0
    assert kf.x[5] == 0.0


def test_kalman_update():
    kf = KalmanFilter()
    z = [0.0, 0.0, 100.0, 0.0, 0.0, -50.0]
    kf.update(z)
    assert kf.x[2] != 0.0
    assert kf.covariance_trace < 9 * 100.0
    assert kf.innovation_consistency


def test_kalman_state():
    kf = KalmanFilter()
    kf.x = [1, 2, 3, 4, 5, 6, 0.1, 0.2, 0.3]
    state = kf.get_state()
    assert state.x == 1
    assert state.z == 3


def test_complementary_filter():
    cf = ComplementaryFilter(alpha=0.98)
    imu = IMUReading(0, 0, 9.81, 0, 0, 0, time.time())
    state = cf.update(imu)
    assert isinstance(state, StateVector)


def test_complementary_filter_convergence():
    cf = ComplementaryFilter(alpha=0.9)
    for _ in range(100):
        imu = IMUReading(0, 0, 9.81, 0, 0, 0, time.time())
        state = cf.update(imu)
    assert abs(state.roll) < 0.5


def test_outlier_rejector():
    orr = OutlierRejector(window_size=10, threshold=3.0)
    for i in range(10):
        orr.check("sensor1", 100.0 + i * 0.1)
    assert orr.check("sensor1", 100.5)
    assert not orr.check("sensor1", 200.0)


def test_pid_controller():
    pid = PIDController(PIDGains(kp=0.05, ki=0.1, kd=0.01))
    output = pid.compute(10.0, 0.1)
    assert output > 0
    output2 = pid.compute(5.0, 0.1)
    assert output2 < output


def test_pid_integral_windup():
    pid = PIDController(PIDGains(kp=0.0, ki=1.0, integral_max=5.0))
    for _ in range(100):
        pid.compute(10.0, 0.1)
    assert pid._integral == 5.0


def test_pid_reset():
    pid = PIDController(PIDGains(kp=1.0, ki=1.0))
    pid.compute(10.0, 0.1)
    pid.reset()
    assert pid._integral == 0.0


def test_attitude_controller():
    ac = AttitudeController()
    current = StateVector(roll=0, pitch=0, yaw=0)
    target = StateVector(roll=0.1, pitch=0.2, yaw=0.3)
    cmd = ac.compute(current, target, 0.01)
    assert cmd.roll_rate != 0
    assert cmd.pitch_rate != 0


def test_trajectory_tracker():
    tt = TrajectoryTracker()
    traj = [
        (0.0, StateVector(x=0, y=0, z=0)),
        (1.0, StateVector(x=10, y=0, z=0)),
        (2.0, StateVector(x=20, y=0, z=0)),
    ]
    tt.load_trajectory(traj)
    target = tt.get_target(0.5)
    assert target.x == 5.0
    target2 = tt.get_target(1.5)
    assert target2.x == 15.0


def test_fault_manager():
    fm = FaultManager()
    faults = []
    fm.on_recovery(lambda f: faults.append(f))

    for _ in range(5):
        fm.detect_fault("engine", 150.0, 100.0, FaultType.ACTUATOR_DEGRADED)

    assert len(faults) == 1
    assert fm.has_active_faults


def test_fault_clear():
    fm = FaultManager()
    for _ in range(5):
        fm.detect_fault("engine", 150.0, 100.0, FaultType.ACTUATOR_DEGRADED)
    assert fm.has_active_faults
    fm.clear_fault("engine")
    assert not fm.has_active_faults


def test_flight_controller_lifecycle():
    fc = FlightController()
    assert not fc._enabled
    fc.enable()
    assert fc._enabled
    fc.disable()
    assert not fc._enabled


def test_flight_controller_command():
    fc = FlightController()
    fc.enable()
    current = StateVector(roll=0, pitch=0, yaw=0)
    target = StateVector(roll=0.1, pitch=0.1, yaw=0.1)
    cmd = fc.compute_command(current, target)
    assert cmd is not None


def test_flight_controller_fault_override():
    fc = FlightController()
    fc.enable()
    fc.fault_manager.detect_fault("engine", 150.0, 100.0, FaultType.ACTUATOR_DEGRADED)
    current = StateVector()
    target = StateVector(roll=0.1)
    cmd = fc.compute_command(current, target)
    assert cmd.throttle == 0.0


def test_flight_controller_trajectory_mode():
    fc = FlightController()
    fc.enable()
    fc.set_mode(ControlMode.TRAJECTORY)
    fc.trajectory.load_trajectory([
        (0.0, StateVector(z=100)),
        (10.0, StateVector(z=0)),
    ])
    current = StateVector(z=100)
    cmd = fc.compute_command(current, StateVector(), time_s=5.0)
    assert cmd is not None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
