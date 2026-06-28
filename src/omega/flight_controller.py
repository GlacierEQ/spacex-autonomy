"""Flight controller — attitude control, trajectory tracking, and fault management.

PID-based attitude controller with integrator anti-windup.
Trajectory following with feedforward and feedback terms.
Fault detection, isolation, and reconfiguration.
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from alpha.state_estimator import StateVector


class ControlMode(Enum):
    ATTITUDE = auto()
    RATE = auto()
    POSITION = auto()
    VELOCITY = auto()
    TRAJECTORY = auto()


class FaultType(Enum):
    SENSOR_DROPOUT = auto()
    ACTUATOR_DEGRADED = auto()
    COMM_LOSS = auto()
    GUIDANCE_ERROR = auto()


@dataclass
class PIDGains:
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    ff: float = 0.0
    output_min: float = -1.0
    output_max: float = 1.0
    integral_max: float = 10.0


class PIDController:
    def __init__(self, gains: PIDGains):
        self.gains = gains
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time: float = 0.0

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0:
            return 0.0

        p = self.gains.kp * error

        self._integral += error * dt
        self._integral = max(-self.gains.integral_max,
                             min(self.gains.integral_max, self._integral))
        i = self.gains.ki * self._integral

        derivative = (error - self._prev_error) / dt
        d = self.gains.kd * derivative

        output = p + i + d + self.gains.ff * error
        output = max(self.gains.output_min, min(self.gains.output_max, output))

        self._prev_error = error
        return output

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0


@dataclass
class ControlCommand:
    timestamp: float
    mode: ControlMode
    roll_rate: float = 0.0
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0
    throttle: float = 0.0
    gimbal_x: float = 0.0
    gimbal_y: float = 0.0


@dataclass
class FaultEvent:
    time: float
    fault_type: FaultType
    subsystem: str
    severity: str
    action: str
    details: dict = field(default_factory=dict)


class AttitudeController:
    def __init__(self):
        self.roll_pid = PIDController(PIDGains(kp=2.0, kd=0.5, ki=0.1))
        self.pitch_pid = PIDController(PIDGains(kp=2.0, kd=0.5, ki=0.1))
        self.yaw_pid = PIDController(PIDGains(kp=1.5, kd=0.3, ki=0.05))
        self._last_time: float = 0.0

    def compute(
        self,
        current: StateVector,
        target: StateVector,
        dt: float = 0.01,
    ) -> ControlCommand:
        if self._last_time == 0:
            self._last_time = time.time()
            dt = 0.01
        else:
            now = time.time()
            dt = now - self._last_time
            self._last_time = now

        roll_err = target.roll - current.roll
        pitch_err = target.pitch - current.pitch
        yaw_err = self._normalize_angle(target.yaw - current.yaw)

        roll_cmd = self.roll_pid.compute(roll_err, dt)
        pitch_cmd = self.pitch_pid.compute(pitch_err, dt)
        yaw_cmd = self.yaw_pid.compute(yaw_err, dt)

        return ControlCommand(
            timestamp=time.time(),
            mode=ControlMode.ATTITUDE,
            roll_rate=roll_cmd,
            pitch_rate=pitch_cmd,
            yaw_rate=yaw_cmd,
        )

    def _normalize_angle(self, angle: float) -> float:
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle


class TrajectoryTracker:
    def __init__(self):
        self.pos_pid = PIDController(PIDGains(kp=0.5, kd=0.2, ki=0.05))
        self.vel_pid = PIDController(PIDGains(kp=0.8, kd=0.1))
        self._trajectory: list[tuple[float, StateVector]] = []
        self._current_idx: int = 0

    def load_trajectory(self, trajectory: list[tuple[float, StateVector]]):
        self._trajectory = sorted(trajectory, key=lambda x: x[0])
        self._current_idx = 0

    def get_target(self, time_s: float) -> Optional[StateVector]:
        if not self._trajectory:
            return None

        while (self._current_idx < len(self._trajectory) - 1 and
               self._trajectory[self._current_idx + 1][0] <= time_s):
            self._current_idx += 1

        if self._current_idx >= len(self._trajectory) - 1:
            return self._trajectory[-1][1]

        t0, s0 = self._trajectory[self._current_idx]
        t1, s1 = self._trajectory[self._current_idx + 1]

        if t1 == t0:
            return s0

        alpha = (time_s - t0) / (t1 - t0)
        return StateVector(
            x=s0.x + alpha * (s1.x - s0.x),
            y=s0.y + alpha * (s1.y - s0.y),
            z=s0.z + alpha * (s1.z - s0.z),
            vx=s0.vx + alpha * (s1.vx - s0.vx),
            vy=s0.vy + alpha * (s1.vy - s0.vy),
            vz=s0.vz + alpha * (s1.vz - s0.vz),
            roll=s0.roll + alpha * (s1.roll - s0.roll),
            pitch=s0.pitch + alpha * (s1.pitch - s0.pitch),
            yaw=s0.yaw + alpha * (s1.yaw - s0.yaw),
        )


class FaultManager:
    def __init__(self):
        self._faults: list[FaultEvent] = []
        self._recovery_callbacks: list[Callable] = []
        self._active_faults: dict[str, FaultEvent] = {}
        self._circuit_breakers: dict[str, int] = {}

    def on_recovery(self, callback: Callable):
        self._recovery_callbacks.append(callback)

    def detect_fault(
        self, subsystem: str, metric: float,
        threshold: float, fault_type: FaultType
    ) -> Optional[FaultEvent]:
        if metric > threshold:
            if subsystem in self._active_faults:
                return None

            self._circuit_breakers[subsystem] = self._circuit_breakers.get(subsystem, 0) + 1

            if self._circuit_breakers[subsystem] >= 3:
                fault = FaultEvent(
                    time=time.time(),
                    fault_type=fault_type,
                    subsystem=subsystem,
                    severity="CRITICAL",
                    action="ISOLATE",
                    details={"metric": metric, "threshold": threshold},
                )
                self._faults.append(fault)
                self._active_faults[subsystem] = fault

                for cb in self._recovery_callbacks:
                    cb(fault)

                return fault
        else:
            self._circuit_breakers[subsystem] = 0

        return None

    def clear_fault(self, subsystem: str) -> bool:
        if subsystem in self._active_faults:
            del self._active_faults[subsystem]
            self._circuit_breakers[subsystem] = 0
            return True
        return False

    @property
    def has_active_faults(self) -> bool:
        return len(self._active_faults) > 0

    @property
    def fault_summary(self) -> dict:
        return {
            "total_faults": len(self._faults),
            "active_faults": len(self._active_faults),
            "subsystems_affected": list(self._active_faults.keys()),
        }


class FlightController:
    def __init__(self):
        self.attitude = AttitudeController()
        self.trajectory = TrajectoryTracker()
        self.fault_manager = FaultManager()
        self._mode = ControlMode.ATTITUDE
        self._enabled = False
        self._command_log: list[ControlCommand] = []

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False
        self.attitude.roll_pid.reset()
        self.attitude.pitch_pid.reset()
        self.attitude.yaw_pid.reset()

    def set_mode(self, mode: ControlMode):
        self._mode = mode

    def compute_command(
        self,
        current: StateVector,
        target: StateVector,
        time_s: float = 0.0,
    ) -> Optional[ControlCommand]:
        if not self._enabled:
            return None

        if self.fault_manager.has_active_faults:
            return ControlCommand(
                timestamp=time.time(),
                mode=ControlMode.ATTITUDE,
                throttle=0.0,
            )

        if self._mode == ControlMode.ATTITUDE:
            cmd = self.attitude.compute(current, target)
        elif self._mode == ControlMode.TRAJECTORY:
            traj_target = self.trajectory.get_target(time_s)
            if traj_target:
                cmd = self.attitude.compute(current, traj_target)
            else:
                cmd = self.attitude.compute(current, target)
        else:
            cmd = self.attitude.compute(current, target)

        self._command_log.append(cmd)
        return cmd

    @property
    def mode(self) -> ControlMode:
        return self._mode

    @property
    def command_count(self) -> int:
        return len(self._command_log)
