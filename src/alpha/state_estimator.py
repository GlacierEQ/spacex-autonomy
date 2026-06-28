"""State estimator — Kalman filter and complementary filter for IMU/GPS fusion.

Fuses accelerometer, gyroscope, and GPS into continuous state estimate.
Handles sensor dropouts and outlier rejection.
Pure math, zero external dependencies.

The Kalman filter was invented in 1960 by Rudolf Kálmán.
It put a man on the moon.
It lands rockets on drone ships.
It guides missiles.
It tracks Santa Claus every December (NORAD uses it).

It is, arguably, the most important algorithm of the 20th century.
And it fits in 100 lines of Python.
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IMUReading:
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    timestamp: float = 0.0


@dataclass
class GPSReading:
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    vel_n: float = 0.0
    vel_e: float = 0.0
    vel_d: float = 0.0
    hdop: float = 1.0
    timestamp: float = 0.0


@dataclass
class StateVector:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    @property
    def speed(self) -> float:
        return math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2)

    @property
    def altitude(self) -> float:
        return self.z

    def as_array(self) -> list[float]:
        return [self.x, self.y, self.z, self.vx, self.vy, self.vz,
                self.roll, self.pitch, self.yaw]


class KalmanFilter:
    def __init__(self, state_dim: int = 9, meas_dim: int = 6):
        self.n = state_dim
        self.m = meas_dim
        self.x = [0.0] * self.n
        self.P = [[100.0 if i == j else 0.0 for j in range(self.n)] for i in range(self.n)]
        self.Q = [[0.1 if i == j else 0.0 for j in range(self.n)] for i in range(self.n)]
        self.R = [[1.0 if i == j else 0.0 for j in range(self.m)] for i in range(self.m)]
        self.H = [[0.0] * self.n for _ in range(self.m)]
        self._setup_measurement_matrix()
        self._last_update: float = 0.0
        self._innovation_log: list[float] = []

    def _setup_measurement_matrix(self):
        for i in range(min(6, self.m)):
            self.H[i][i] = 1.0

    def predict(self, dt: float):
        F = [[1.0 if i == j else (dt if i == j + 3 and i < 3 else 0.0)
              for j in range(self.n)] for i in range(self.n)]

        new_x = _mat_vec_mul(F, self.x)
        self.x = new_x

        Ft = _mat_transpose(F)
        FP = _mat_mul(F, self.P)
        FPt = _mat_mul(FP, Ft)
        self.P = _mat_add(FPt, self.Q)

    def update(self, z: list[float]):
        y = _vec_sub(z, _mat_vec_mul(self.H, self.x))

        Ht = _mat_transpose(self.H)
        HP = _mat_mul(self.H, self.P)
        HPHt = _mat_mul(HP, Ht)
        S = _mat_add(HPHt, self.R)
        S_inv = _invert_matrix(S)

        PHt = _mat_mul(self.P, Ht)
        K = _mat_mul(PHt, S_inv)

        Ky = _mat_vec_mul(K, y)
        self.x = _vec_add(self.x, Ky)

        KH = _mat_mul(K, self.H)
        I_KH = _mat_sub(_identity(self.n), _pad_matrix(KH, self.n, self.n))
        self.P = _mat_mul(I_KH, self.P)

        innovation_norm = math.sqrt(sum(v ** 2 for v in y))
        self._innovation_log.append(innovation_norm)

    def get_state(self) -> StateVector:
        return StateVector(
            x=self.x[0], y=self.x[1], z=self.x[2],
            vx=self.x[3], vy=self.x[4], vz=self.x[5],
            roll=self.x[6], pitch=self.x[7], yaw=self.x[8],
        )

    @property
    def covariance_trace(self) -> float:
        return sum(self.P[i][i] for i in range(self.n))

    @property
    def innovation_consistency(self) -> bool:
        if len(self._innovation_log) < 5:
            return True
        recent = self._innovation_log[-5:]
        avg = sum(recent) / len(recent)
        return avg < 10.0


def _invert_matrix(A: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan elimination with partial pivoting."""
    n = len(A)
    result = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    a = [row[:] for row in A]

    for i in range(n):
        max_row = i
        for k in range(i + 1, n):
            if abs(a[k][i]) > abs(a[max_row][i]):
                max_row = k
        a[i], a[max_row] = a[max_row], a[i]
        result[i], result[max_row] = result[max_row], result[i]

        if abs(a[i][i]) < 1e-12:
            continue

        pivot = a[i][i]
        a[i] = [x / pivot for x in a[i]]
        result[i] = [x / pivot for x in result[i]]

        for k in range(n):
            if k != i:
                factor = a[k][i]
                a[k] = [a[k][j] - factor * a[i][j] for j in range(n)]
                result[k] = [result[k][j] - factor * result[i][j] for j in range(n)]

    return result


def _mat_mul(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    rows_a, cols_a = len(A), len(A[0])
    cols_b = len(B[0])
    result = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            result[i][j] = sum(A[i][k] * B[k][j] for k in range(cols_a))
    return result


def _mat_transpose(A: list[list[float]]) -> list[list[float]]:
    return [[A[j][i] for j in range(len(A))] for i in range(len(A[0]))]


def _mat_add(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    return [[A[i][j] + B[i][j] for j in range(len(A[0]))] for i in range(len(A))]


def _mat_sub(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    return [[A[i][j] - B[i][j] for j in range(len(A[0]))] for i in range(len(A))]


def _mat_vec_mul(A: list[list[float]], v: list[float]) -> list[float]:
    return [sum(A[i][j] * v[j] for j in range(len(v))) for i in range(len(A))]


def _vec_add(a: list[float], b: list[float]) -> list[float]:
    return [a[i] + b[i] for i in range(len(a))]


def _vec_sub(a: list[float], b: list[float]) -> list[float]:
    return [a[i] - b[i] for i in range(len(a))]


def _identity(n: int) -> list[list[float]]:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _pad_matrix(A: list[list[float]], rows: int, cols: int) -> list[list[float]]:
    result = [[0.0] * cols for _ in range(rows)]
    for i in range(min(len(A), rows)):
        for j in range(min(len(A[0]), cols)):
            result[i][j] = A[i][j]
    return result


class ComplementaryFilter:
    def __init__(self, alpha: float = 0.98):
        self.alpha = alpha
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._last_time: float = 0.0

    def update(self, imu: IMUReading, gps: Optional[GPSReading] = None) -> StateVector:
        now = imu.timestamp if imu.timestamp > 0 else time.time()

        if self._last_time == 0:
            self._last_time = now
            accel_roll = math.atan2(imu.accel_y, imu.accel_z)
            accel_pitch = math.atan2(-imu.accel_x, math.sqrt(imu.accel_y ** 2 + imu.accel_z ** 2))
            self._roll = accel_roll
            self._pitch = accel_pitch
            self._yaw = 0.0
            return StateVector(roll=self._roll, pitch=self._pitch, yaw=self._yaw)

        dt = now - self._last_time
        self._last_time = now

        accel_roll = math.atan2(imu.accel_y, imu.accel_z)
        accel_pitch = math.atan2(-imu.accel_x, math.sqrt(imu.accel_y ** 2 + imu.accel_z ** 2))

        self._roll = self.alpha * (self._roll + imu.gyro_x * dt) + (1 - self.alpha) * accel_roll
        self._pitch = self.alpha * (self._pitch + imu.gyro_y * dt) + (1 - self.alpha) * accel_pitch
        self._yaw += imu.gyro_z * dt

        vx = gps.vel_n if gps else 0.0
        vy = gps.vel_e if gps else 0.0
        vz = gps.vel_d if gps else 0.0

        return StateVector(
            x=gps.lon if gps else 0.0,
            y=gps.lat if gps else 0.0,
            z=gps.alt if gps else 0.0,
            vx=vx, vy=vy, vz=vz,
            roll=self._roll, pitch=self._pitch, yaw=self._yaw,
        )


class OutlierRejector:
    def __init__(self, window_size: int = 10, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold
        self._buffers: dict[str, list[float]] = {}

    def check(self, key: str, value: float) -> bool:
        if key not in self._buffers:
            self._buffers[key] = []

        buf = self._buffers[key]

        if len(buf) >= 5:
            mean = sum(buf) / len(buf)
            var = sum((v - mean) ** 2 for v in buf) / len(buf)
            std = math.sqrt(var) if var > 0 else 1e-10
            if abs(value - mean) / std >= self.threshold:
                return False

        buf.append(value)
        if len(buf) > self.window_size:
            buf.pop(0)

        return True
