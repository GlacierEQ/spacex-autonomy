from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_readme_contract import verify_readme

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "LOCAL_AUTONOMY_SIMULATION_NOT_FLIGHT_CONTROL_AUTHORITY"
APPROVED_CAPABILITIES = [
    "deterministic-local-autonomy-mode-policy-and-hysteresis",
    "one-dimensional-state-estimation-and-bounded-position-control",
    "weighted-local-multi-vehicle-estimate-fusion",
    "concurrency-safe-go-phase-threshold-simulation",
]
APPROVED_SCOPE = [
    "deterministic Python autonomy mode policy and hysteresis",
    "one-dimensional alpha-beta state estimation",
    "bounded local position-control simulation",
    "weighted multi-vehicle estimate fusion",
    "concurrency-safe Go phase and threshold simulation",
]
APPROVED_NONCLAIMS = [
    "no SpaceX affiliation, endorsement, employment, or proprietary access",
    "no real vehicle, actuator, telemetry bus, flight computer, or external command output",
    "no navigation-grade estimator or validated mission thresholds",
    "no adversarial Byzantine consensus guarantee",
    "no operational launch, re-entry, landing, or abort authority",
    "no hardware-in-the-loop, deployment, reliability, or performance proof",
]
REQUIRED_RECEIPTS = [
    "Autonomy Simulation Verification",
    "Python 3.11 positive-count TEST receipt",
    "Python 3.12 positive-count TEST receipt",
    "Python 3.13 positive-count TEST receipt",
    "Go native positive-count TEST receipt with race_enabled=true",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_preserves_independent_non_flight_boundary() -> None:
    assert verify_readme(ROOT / "README.md") == ()


def test_machine_capability_surface_is_exact_whitelist() -> None:
    payload = json.loads(read("machine/capabilities.json"))
    assert payload["evidence_state"] == TOKEN
    assert payload["capabilities"] == APPROVED_CAPABILITIES


def test_machine_state_requires_external_current_head_receipt() -> None:
    state = json.loads(read("machine/excellence-state.json"))
    assert state["state"] == "TESTED"
    assert state["principal_state"] == "TESTED"
    assert state["evidence_state"] == TOKEN
    for gate in (
        "PYTHON_PACKAGE_PROOF",
        "PYTHON_POSITIVE_TEST_RECEIPT",
        "PUBLIC_README_BOUNDARY",
    ):
        assert state["gates"][gate] == "REQUIRES_CURRENT_HEAD_RECEIPT"
    assert state["gates"]["GO_NATIVE_BUILD_AND_RACE_TEST"] == (
        "REQUIRES_CURRENT_HEAD_RACE_RECEIPT"
    )
    assert state["gates"]["EXTERNAL_COMMAND_AUTHORITY"] == "NOT_CLAIMED"
    assert state["gates"]["PRODUCTION_DEPLOYMENT"] == "NOT_PROVEN"
    receipt = state["proof_receipt"]
    assert receipt["state"] == "EXTERNAL_EXACT_HEAD_RECEIPT_REQUIRED"
    assert receipt["required"] == REQUIRED_RECEIPTS
    assert "race_enabled=true" in receipt["binding_rule"]
    assert "never self-asserts" in receipt["binding_rule"]


def test_target_contract_is_an_exact_allowlist() -> None:
    contract = json.loads(read("machine/target-contract.json"))
    assert contract["current"] == {
        "state": "TESTED",
        "implemented": True,
        "tested": True,
        "deployed": False,
    }
    assert contract["evidence_state"] == TOKEN
    assert contract["verified_scope"] == APPROVED_SCOPE
    assert contract["nonclaims"] == APPROVED_NONCLAIMS
    assert contract["proof_contract"] == {
        "python_versions": ["3.11", "3.12", "3.13"],
        "python_positive_count_receipt_required": True,
        "go_positive_count_receipt_required": True,
        "go_race_enabled_required": True,
        "exact_canonical_head_required": True,
    }
    assert contract["next_gate"] == (
        "exact-current-head Python receipts plus Go race-enabled native receipt"
    )
