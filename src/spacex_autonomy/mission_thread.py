"""Deterministic mission-thread quorum for simulated GO/HOLD review.

This is a portfolio simulation boundary. It does not command vehicles, launch
systems, actuators, or operational mission-control infrastructure.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum

MISSION_THREAD_SCHEMA = "glaciereq.spacex-autonomy.mission-thread-quorum.v1"
MISSION_THREAD_EVIDENCE_STATE = "LOCAL_SIMULATION_GO_HOLD_QUORUM_NO_FLIGHT_AUTHORITY"


class MissionDecision(StrEnum):
    GO = "GO"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class MissionVote:
    source_id: str
    decision: MissionDecision | str
    confidence: float
    reason: str

    def validate(self) -> MissionDecision:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be non-empty text")
        try:
            decision = MissionDecision(self.decision)
        except (TypeError, ValueError) as exc:
            raise ValueError("decision must be GO or HOLD") from exc
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise ValueError("confidence must be a finite real number")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and in 0..1")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty text")
        return decision


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compile_mission_thread(
    votes: list[MissionVote],
    *,
    min_sources: int = 3,
    min_go_weight: float = 0.67,
    hold_veto_confidence: float = 0.90,
) -> dict[str, object]:
    """Compile conflicting simulated subsystem votes into a reviewable GO/HOLD result."""

    if isinstance(min_sources, bool) or not isinstance(min_sources, int) or min_sources < 1:
        raise ValueError("min_sources must be a positive integer")
    for name, value in (
        ("min_go_weight", min_go_weight),
        ("hold_veto_confidence", hold_veto_confidence),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite real number")
        numeric = float(value)
        if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
            raise ValueError(f"{name} must be finite and in 0..1")

    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    total_weight = 0.0
    go_weight = 0.0
    vetoes: list[str] = []
    hold_reasons: list[str] = []

    for vote in votes:
        decision = vote.validate()
        source = vote.source_id.strip()
        if source in seen:
            raise ValueError("source_id values must be unique")
        seen.add(source)
        confidence = float(vote.confidence)
        total_weight += confidence
        if decision is MissionDecision.GO:
            go_weight += confidence
        else:
            hold_reasons.append(f"{source}: {vote.reason.strip()}")
            if confidence >= hold_veto_confidence:
                vetoes.append(source)
        normalized.append(
            {
                "source_id": source,
                "decision": decision.value,
                "confidence": confidence,
                "reason": vote.reason.strip(),
            }
        )

    source_count = len(normalized)
    go_fraction = (go_weight / total_weight) if total_weight > 0 else 0.0

    if source_count < min_sources:
        decision = MissionDecision.HOLD
        basis = "INSUFFICIENT_SOURCE_QUORUM"
    elif vetoes:
        decision = MissionDecision.HOLD
        basis = "HIGH_CONFIDENCE_HOLD_VETO"
    elif total_weight <= 0:
        decision = MissionDecision.HOLD
        basis = "ZERO_CONFIDENCE_QUORUM"
    elif go_fraction < min_go_weight:
        decision = MissionDecision.HOLD
        basis = "GO_WEIGHT_BELOW_THRESHOLD"
    else:
        decision = MissionDecision.GO
        basis = "WEIGHTED_GO_QUORUM"

    body: dict[str, object] = {
        "schema": MISSION_THREAD_SCHEMA,
        "decision": decision.value,
        "basis": basis,
        "source_count": source_count,
        "go_weight_fraction": round(go_fraction, 4),
        "min_sources": min_sources,
        "min_go_weight": float(min_go_weight),
        "hold_veto_confidence": float(hold_veto_confidence),
        "veto_sources": sorted(vetoes),
        "hold_reasons": sorted(hold_reasons),
        "votes": normalized,
        "evidence_state": MISSION_THREAD_EVIDENCE_STATE,
        "operational_authority": False,
        "vehicle_command": False,
    }
    body["receipt_sha256"] = _digest(body)
    return body
