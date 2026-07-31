from __future__ import annotations

from pathlib import Path

from mastermind_sidecar import MODULE_PATHS, MastermindSidecar


def test_repository_sidecar_reports_all_verified_modules() -> None:
    sidecar = MastermindSidecar()
    report = sidecar.health_report()
    assert report["status"] == "healthy"
    assert report["modules_present"] == len(MODULE_PATHS)
    assert report["modules_expected"] == len(MODULE_PATHS)
    assert report["external_registration_verified"] is False
    for evidence in report["module_evidence"].values():
        assert evidence["present"] is True
        assert len(evidence["sha256"]) == 64


def test_missing_local_modules_produce_degraded_status(tmp_path: Path) -> None:
    sidecar = MastermindSidecar(repository_root=tmp_path)
    report = sidecar.health_report()
    assert report["status"] == "degraded"
    assert report["modules_present"] == 0


def test_status_is_stable_json_text() -> None:
    payload = MastermindSidecar().status()
    assert '"schema": "glaciereq.repository-local-health.v1"' in payload
    assert '"status": "healthy"' in payload
