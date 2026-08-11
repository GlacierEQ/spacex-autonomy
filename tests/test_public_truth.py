from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "LOCAL_AUTONOMY_SIMULATION_NOT_FLIGHT_CONTROL_AUTHORITY"
APPROVED_CAPABILITIES = [
    "deterministic-local-autonomy-mode-policy-and-hysteresis",
    "one-dimensional-state-estimation-and-bounded-position-control",
    "weighted-local-multi-vehicle-estimate-fusion",
    "concurrency-safe-go-phase-threshold-simulation",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_preserves_independent_non_flight_boundary() -> None:
    readme = read("README.md")
    assert "This is an independent portfolio project" in readme
    assert "does not claim SpaceX employment, endorsement, affiliation" in readme
    assert "It does not contact a vehicle, network, provider, or external control system" in readme
    assert "Simulation output is not operational flight guidance" in readme


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
        "GO_NATIVE_BUILD_AND_RACE_TEST",
        "PUBLIC_README_BOUNDARY",
    ):
        assert state["gates"][gate] == "REQUIRES_CURRENT_HEAD_RECEIPT"
    assert state["gates"]["EXTERNAL_COMMAND_AUTHORITY"] == "NOT_CLAIMED"
    assert state["gates"]["PRODUCTION_DEPLOYMENT"] == "NOT_PROVEN"
    receipt = state["proof_receipt"]
    assert receipt["state"] == "EXTERNAL_EXACT_HEAD_RECEIPT_REQUIRED"
    assert receipt["required"] == ["Autonomy Simulation Verification"]
    assert "never self-asserts" in receipt["binding_rule"]


def test_target_contract_is_tested_not_promoted() -> None:
    contract = json.loads(read("machine/target-contract.json"))
    assert contract["current"]["state"] == "TESTED"
    assert contract["evidence_state"] == TOKEN
    assert contract["next_gate"] == "exact-current-head Python and Go native proof receipts"
    nonclaims = "\n".join(contract["nonclaims"])
    assert "no real vehicle" in nonclaims
    assert "no operational launch" in nonclaims
