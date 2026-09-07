from __future__ import annotations

import pytest

from spacex_autonomy.mission_thread import (
    MISSION_THREAD_EVIDENCE_STATE,
    MissionVote,
    compile_mission_thread,
)


def test_weighted_go_quorum_is_deterministic_and_non_operational() -> None:
    votes = [
        MissionVote("guidance", "GO", 0.9, "trajectory nominal"),
        MissionVote("thermal", "GO", 0.8, "thermal margins nominal"),
        MissionVote("range", "GO", 0.7, "range clear"),
    ]
    first = compile_mission_thread(votes)
    second = compile_mission_thread(votes)
    assert first == second
    assert first["decision"] == "GO"
    assert first["basis"] == "WEIGHTED_GO_QUORUM"
    assert first["evidence_state"] == MISSION_THREAD_EVIDENCE_STATE
    assert first["operational_authority"] is False
    assert first["vehicle_command"] is False
    assert len(first["receipt_sha256"]) == 64


def test_high_confidence_hold_vote_vetoes_go_majority() -> None:
    result = compile_mission_thread(
        [
            MissionVote("guidance", "GO", 1.0, "trajectory nominal"),
            MissionVote("thermal", "GO", 1.0, "thermal nominal"),
            MissionVote("range", "HOLD", 0.95, "range unavailable"),
        ]
    )
    assert result["decision"] == "HOLD"
    assert result["basis"] == "HIGH_CONFIDENCE_HOLD_VETO"
    assert result["veto_sources"] == ["range"]
    assert result["hold_reasons"] == ["range: range unavailable"]


def test_conflicted_low_weight_go_result_holds() -> None:
    result = compile_mission_thread(
        [
            MissionVote("guidance", "GO", 0.4, "partial"),
            MissionVote("thermal", "HOLD", 0.5, "margin low"),
            MissionVote("range", "GO", 0.1, "weak signal"),
        ]
    )
    assert result["decision"] == "HOLD"
    assert result["basis"] == "GO_WEIGHT_BELOW_THRESHOLD"


def test_insufficient_sources_hold_even_when_all_vote_go() -> None:
    result = compile_mission_thread(
        [
            MissionVote("guidance", "GO", 1.0, "nominal"),
            MissionVote("range", "GO", 1.0, "clear"),
        ],
        min_sources=3,
    )
    assert result["decision"] == "HOLD"
    assert result["basis"] == "INSUFFICIENT_SOURCE_QUORUM"


def test_duplicate_and_malformed_votes_fail_closed() -> None:
    with pytest.raises(ValueError, match="unique"):
        compile_mission_thread(
            [
                MissionVote("range", "GO", 1.0, "clear"),
                MissionVote("range", "HOLD", 1.0, "blocked"),
                MissionVote("thermal", "GO", 1.0, "nominal"),
            ]
        )
    with pytest.raises(ValueError, match="confidence"):
        compile_mission_thread(
            [
                MissionVote("a", "GO", float("nan"), "bad"),
                MissionVote("b", "GO", 1.0, "ok"),
                MissionVote("c", "GO", 1.0, "ok"),
            ]
        )
