# SpaceX Autonomy

Autonomous flight systems — state estimation, attitude control, and fault management.

## Architecture

**Double Helix (Alpha + Omega)**

- **Alpha** (`src/alpha/state_estimator.py`): Kalman filter, complementary filter, outlier rejection for IMU/GPS fusion.
- **Omega** (`src/omega/flight_controller.py`): PID attitude control, trajectory tracking, fault detection with circuit breaker.

## Features

- 9-state Kalman filter for position/velocity/attitude
- Complementary filter for attitude estimation
- 3-sigma outlier rejection
- PID controllers with anti-windup
- Trajectory following with linear interpolation
- Fault detection with circuit breaker pattern
- Fault isolation and recovery
- Zero external dependencies
