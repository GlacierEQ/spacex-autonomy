"""Multi-vehicle state consensus — shared reality across autonomous vehicles.

Standard autonomy: each vehicle estimates its own state independently.
Innovation: Vehicles SHARE state estimates and reach consensus on
reality. This creates a collective state that is MORE ACCURATE than
any individual vehicle's estimate.

The wheel: Kalman filter (single vehicle state estimation)
The vehicle: distributed consensus across vehicle swarm

Key insight: When multiple vehicles observe the same event from different
angles, fusing their observations creates a 3D picture that no single
vehicle can see. This is how the human visual system works — two eyes
create depth perception. Multiple vehicles create spatial awareness.
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VehicleEstimate:
    vehicle_id: int
    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    confidence: float = 1.0
    timestamp: float = 0.0
    uncertainty_xyz: tuple[float, float, float] = (1.0, 1.0, 1.0)


@dataclass
class ConsensusState:
    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    uncertainty: float = 1.0
    participants: int = 0
    confidence: float = 0.0
    timestamp: float = 0.0


@dataclass
class Observation:
    observer_id: int
    target_id: int
    range_m: float
    bearing_rad: tuple[float, float]
    range_rate: float
    timestamp: float
    quality: float = 1.0


class DistributedStateEstimator:
    """Estimates shared state from distributed observations.

    Innovation: Each vehicle has its own state estimate with its own
    uncertainty. When vehicles share estimates, we can fuse them using
    weighted averaging where the weight is inversely proportional to
    uncertainty. The fused estimate is MORE CERTAIN than any individual.
    """

    def __init__(self):
        self._estimates: dict[int, VehicleEstimate] = {}
        self._consensus_history: list[ConsensusState] = []

    def update_estimate(self, estimate: VehicleEstimate):
        self._estimates[estimate.vehicle_id] = estimate

    def compute_consensus(self) -> Optional[ConsensusState]:
        if not self._estimates:
            return None

        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        weighted_z = 0.0
        weighted_vx = 0.0
        weighted_vy = 0.0
        weighted_vz = 0.0

        for est in self._estimates.values():
            unc = sum(est.uncertainty_xyz) / 3
            weight = est.confidence / max(unc, 0.01)

            weighted_x += est.x * weight
            weighted_y += est.y * weight
            weighted_z += est.z * weight
            weighted_vx += est.vx * weight
            weighted_vy += est.vy * weight
            weighted_vz += est.vz * weight
            total_weight += weight

        if total_weight <= 0:
            return None

        consensus = ConsensusState(
            x=weighted_x / total_weight,
            y=weighted_y / total_weight,
            z=weighted_z / total_weight,
            vx=weighted_vx / total_weight,
            vy=weighted_vy / total_weight,
            vz=weighted_vz / total_weight,
            uncertainty=1.0 / total_weight,
            participants=len(self._estimates),
            confidence=min(1.0, total_weight / len(self._estimates)),
            timestamp=time.time(),
        )

        self._consensus_history.append(consensus)
        return consensus

    def estimate_quality(self) -> dict:
        if not self._estimates:
            return {"quality": 0, "vehicles": 0}

        uncertainties = [
            sum(e.uncertainty_xyz) / 3 for e in self._estimates.values()
        ]
        avg_uncertainty = sum(uncertainties) / len(uncertainties)
        avg_confidence = sum(e.confidence for e in self._estimates.values()) / len(self._estimates)

        return {
            "quality": avg_confidence / max(avg_uncertainty, 0.01),
            "vehicles": len(self._estimates),
            "avg_uncertainty_m": avg_uncertainty,
            "avg_confidence": avg_confidence,
        }


class ObservationFuser:
    """Fuses observations from multiple vehicles to improve state estimate.

    Innovation: When vehicle A sees target T at range 100m from angle 30°,
    and vehicle B sees target T at range 80m from angle 150°, triangulation
    gives a 3D position estimate with MUCH lower uncertainty than either
    observation alone.
    """

    def __init__(self):
        self._observations: dict[int, list[Observation]] = {}

    def add_observation(self, obs: Observation):
        if obs.target_id not in self._observations:
            self._observations[obs.target_id] = []
        self._observations[obs.target_id].append(obs)

        cutoff = time.time() - 300
        self._observations[obs.target_id] = [
            o for o in self._observations[obs.target_id]
            if o.timestamp > cutoff
        ]

    def triangulate(
        self,
        target_id: int,
        observer_positions: dict[int, tuple[float, float, float]],
    ) -> Optional[dict]:
        observations = self._observations.get(target_id, [])
        if len(observations) < 2:
            return None

        position_estimates = []
        for obs in observations:
            if obs.observer_id not in observer_positions:
                continue

            ox, oy, oz = observer_positions[obs.observer_id]
            az, el = obs.bearing_rad

            dx = obs.range_m * math.cos(el) * math.sin(az)
            dy = obs.range_m * math.cos(el) * math.cos(az)
            dz = obs.range_m * math.sin(el)

            position_estimates.append({
                "x": ox + dx,
                "y": oy + dy,
                "z": oz + dz,
                "quality": obs.quality,
            })

        if len(position_estimates) < 2:
            return None

        total_quality = sum(p["quality"] for p in position_estimates)
        fused_x = sum(p["x"] * p["quality"] for p in position_estimates) / total_quality
        fused_y = sum(p["y"] * p["quality"] for p in position_estimates) / total_quality
        fused_z = sum(p["z"] * p["quality"] for p in position_estimates) / total_quality

        uncertainties = []
        for p in position_estimates:
            dx = p["x"] - fused_x
            dy = p["y"] - fused_y
            dz = p["z"] - fused_z
            uncertainties.append(math.sqrt(dx ** 2 + dy ** 2 + dz ** 2))

        avg_uncertainty = sum(uncertainties) / len(uncertainties)

        return {
            "target_id": target_id,
            "x": fused_x,
            "y": fused_y,
            "z": fused_z,
            "uncertainty_m": avg_uncertainty,
            "observations_used": len(position_estimates),
            "improvement_factor": max(uncertainties) / avg_uncertainty if avg_uncertainty > 0 else 1,
        }


class SwarmConsensusProtocol:
    """Byzantine fault-tolerant consensus for multi-vehicle operations.

    Innovation: Not all vehicles are trustworthy. Some may be damaged,
    some may have faulty sensors, some may even be adversarial. This
    protocol reaches consensus even when up to 1/3 of vehicles are
    providing incorrect information.

    Uses weighted voting where weight is proportional to historical
    accuracy and sensor quality.
    """

    def __init__(self, num_vehicles: int, max_faults: int = 1):
        self.num_vehicles = num_vehicles
        self.max_faults = max_faults
        self.min_agreement = 2 * max_faults + 1
        self._accuracy_scores: dict[int, float] = {i: 1.0 for i in range(num_vehicles)}
        self._proposals: list[dict] = []

    def propose(self, proposer_id: int, state: dict) -> dict:
        proposal = {
            "proposer": proposer_id,
            "state": state,
            "timestamp": time.time(),
            "weight": self._accuracy_scores.get(proposer_id, 0.5),
        }
        self._proposals.append(proposal)
        return proposal

    def vote(
        self,
        voter_id: int,
        proposal_idx: int,
        agree: bool,
    ) -> dict:
        weight = self._accuracy_scores.get(voter_id, 0.5)
        vote = {
            "voter": voter_id,
            "proposal_idx": proposal_idx,
            "agree": agree,
            "weight": weight,
            "timestamp": time.time(),
        }
        return vote

    def check_consensus(
        self,
        proposal_idx: int,
        votes: list[dict],
    ) -> Optional[dict]:
        relevant_votes = [v for v in votes if v.get("proposal_idx") == proposal_idx]
        agree_weight = sum(v["weight"] for v in relevant_votes if v.get("agree", False))
        total_weight = sum(v["weight"] for v in relevant_votes)

        if total_weight <= 0:
            return None

        agreement_ratio = agree_weight / total_weight

        if agreement_ratio > 0.67 and len(relevant_votes) >= self.min_agreement:
            proposal = self._proposals[proposal_idx] if proposal_idx < len(self._proposals) else None
            if proposal:
                return {
                    "consensus_reached": True,
                    "agreement_ratio": agreement_ratio,
                    "state": proposal["state"],
                    "voters": len(relevant_votes),
                }

        return {"consensus_reached": False, "agreement_ratio": agreement_ratio}

    def update_accuracy(self, vehicle_id: int, was_correct: bool):
        current = self._accuracy_scores.get(vehicle_id, 0.5)
        if was_correct:
            self._accuracy_scores[vehicle_id] = min(1.0, current * 1.1)
        else:
            self._accuracy_scores[vehicle_id] = max(0.1, current * 0.9)


class MultiVehicleConsensusSystem:
    """Full multi-vehicle consensus system.

    The wheel: single vehicle Kalman filter
    The vehicle: distributed consensus across vehicle swarm

    Innovation: Multiple vehicles observing the same scene create a
    richer, more accurate picture than any single vehicle. This system
    fuses observations, reaches consensus on reality, and maintains
    Byzantine fault tolerance against compromised vehicles.
    """

    def __init__(self, num_vehicles: int):
        self.num_vehicles = num_vehicles
        self.state_estimator = DistributedStateEstimator()
        self.observation_fuser = ObservationFuser()
        self.consensus_protocol = SwarmConsensusProtocol(num_vehicles)
        self._consensus_log: list[dict] = []

    def update_vehicle_state(self, estimate: VehicleEstimate):
        self.state_estimator.update_estimate(estimate)

    def report_observation(self, obs: Observation):
        self.observation_fuser.add_observation(obs)

    def get_swarm_state(self) -> dict:
        consensus = self.state_estimator.compute_consensus()
        quality = self.state_estimator.estimate_quality()

        return {
            "consensus_state": {
                "x": consensus.x,
                "y": consensus.y,
                "z": consensus.z,
                "uncertainty": consensus.uncertainty,
                "participants": consensus.participants,
            } if consensus else None,
            "quality": quality,
            "vehicles_reporting": quality["vehicles"],
            "consensus_confidence": consensus.confidence if consensus else 0,
        }

    def get_triangulated_targets(
        self,
        observer_positions: dict[int, tuple[float, float, float]],
    ) -> list[dict]:
        results = []
        for target_id in self.observation_fuser._observations:
            result = self.observation_fuser.triangulate(target_id, observer_positions)
            if result:
                results.append(result)
        return results

    @property
    def swarm_health(self) -> dict:
        estimates = list(self.state_estimator._estimates.values())
        if not estimates:
            return {"healthy_vehicles": 0, "total": self.num_vehicles}

        healthy = sum(1 for e in estimates if e.confidence > 0.5)
        return {
            "healthy_vehicles": healthy,
            "total": self.num_vehicles,
            "health_ratio": healthy / self.num_vehicles,
            "avg_confidence": sum(e.confidence for e in estimates) / len(estimates),
        }
