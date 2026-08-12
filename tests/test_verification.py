from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_go_test_json import MAX_GO_TEST_BYTES, verify_go_test_json
from scripts.verify_junit import MAX_JUNIT_BYTES, verify_junit
from scripts.verify_readme_contract import (
    HEADINGS,
    REQUIRED_BOUNDARY,
    REQUIRED_EVIDENCE,
    verify_readme,
)


def _write_junit(
    path: Path,
    *,
    passed: int = 1,
    skipped: int = 0,
    failed: int = 0,
) -> None:
    cases: list[str] = []
    cases.extend(f'<testcase name="pass-{index}" />' for index in range(passed))
    cases.extend(
        f'<testcase name="skip-{index}"><skipped /></testcase>' for index in range(skipped)
    )
    cases.extend(f'<testcase name="fail-{index}"><failure /></testcase>' for index in range(failed))
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite name="suite">' + "".join(cases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )


def _write_go_events(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def _valid_readme() -> str:
    return "\n".join((*HEADINGS, *REQUIRED_EVIDENCE, *REQUIRED_BOUNDARY)) + "\n"


def test_positive_count_receipt_is_verified_and_atomic(tmp_path: Path) -> None:
    junit = tmp_path / "pytest.xml"
    receipt_path = tmp_path / "receipt.json"
    _write_junit(junit, passed=4, skipped=1)
    receipt = verify_junit(
        junit,
        receipt_path,
        pytest_exit_code=0,
        commit_sha="a" * 40,
        python_version="3.13",
    )
    assert receipt["conclusion"] == "VERIFIED"
    assert receipt["tests"] == 5
    assert receipt["executed"] == 4
    assert len(receipt["junit_sha256"]) == 64
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt
    assert list(tmp_path.glob(".receipt.json.*.tmp")) == []


def test_zero_or_all_skipped_tests_cannot_establish_test_evidence(tmp_path: Path) -> None:
    for index, skipped in enumerate((0, 3)):
        junit = tmp_path / f"pytest-{index}.xml"
        _write_junit(junit, passed=0, skipped=skipped)
        receipt = verify_junit(
            junit,
            tmp_path / f"receipt-{index}.json",
            pytest_exit_code=0,
            commit_sha="b" * 40,
            python_version="3.12",
        )
        assert receipt["conclusion"] == "UNVERIFIED_ZERO_PROOF"


def test_failed_testcase_cannot_produce_verified_receipt(tmp_path: Path) -> None:
    junit = tmp_path / "pytest.xml"
    _write_junit(junit, passed=1, failed=1)
    receipt = verify_junit(
        junit,
        tmp_path / "receipt.json",
        pytest_exit_code=1,
        commit_sha="c" * 40,
        python_version="3.11",
    )
    assert receipt["conclusion"] == "FAILED"
    assert receipt["failures"] == 1


def test_entity_non_utf8_and_oversized_reports_fail_closed(tmp_path: Path) -> None:
    entity = tmp_path / "entity.xml"
    entity.write_text(
        '<!DOCTYPE testsuite [<!ENTITY x "expanded">]><testsuite />',
        encoding="utf-8",
    )
    utf16 = tmp_path / "utf16.xml"
    utf16.write_bytes("<testsuite />".encode("utf-16"))
    oversized = tmp_path / "oversized.xml"
    oversized.write_bytes(b" " * (MAX_JUNIT_BYTES + 1))

    for index, path in enumerate((entity, utf16, oversized)):
        receipt = verify_junit(
            path,
            tmp_path / f"receipt-{index}.json",
            pytest_exit_code=0,
            commit_sha="d" * 40,
            python_version="3.13",
        )
        assert receipt["conclusion"] == "FAILED"


def test_positive_go_event_stream_creates_race_test_evidence(tmp_path: Path) -> None:
    report = tmp_path / "go-test.json"
    output = tmp_path / "go-receipt.json"
    _write_go_events(
        report,
        [
            {"Action": "pass", "Package": "autonomy", "Test": "TestOne"},
            {"Action": "pass", "Package": "autonomy", "Test": "TestTwo"},
            {"Action": "pass", "Package": "autonomy"},
        ],
    )
    receipt = verify_go_test_json(
        report,
        output,
        go_test_exit_code=0,
        commit_sha="e" * 40,
        go_version="go1.23.4",
        race_enabled=True,
    )
    assert receipt["conclusion"] == "VERIFIED"
    assert receipt["race_enabled"] is True
    assert receipt["passed"] == 2
    assert receipt["executed"] == 2
    assert len(receipt["report_sha256"]) == 64
    assert json.loads(output.read_text(encoding="utf-8")) == receipt


def test_non_race_go_execution_cannot_establish_test_evidence(tmp_path: Path) -> None:
    report = tmp_path / "go-test.json"
    _write_go_events(
        report,
        [{"Action": "pass", "Package": "autonomy", "Test": "TestOne"}],
    )
    receipt = verify_go_test_json(
        report,
        tmp_path / "receipt.json",
        go_test_exit_code=0,
        commit_sha="e" * 40,
        go_version="go1.23.4",
        race_enabled=False,
    )
    assert receipt["conclusion"] == "FAILED"
    assert receipt["race_enabled"] is False
    assert "race-enabled" in receipt["reason"]


def test_zero_go_tests_cannot_establish_test_evidence(tmp_path: Path) -> None:
    report = tmp_path / "go-test.json"
    _write_go_events(report, [{"Action": "pass", "Package": "autonomy"}])
    receipt = verify_go_test_json(
        report,
        tmp_path / "go-receipt.json",
        go_test_exit_code=0,
        commit_sha="f" * 40,
        go_version="go1.23.4",
        race_enabled=True,
    )
    assert receipt["conclusion"] == "UNVERIFIED_ZERO_PROOF"


def test_failed_or_malformed_go_events_fail_closed(tmp_path: Path) -> None:
    failed = tmp_path / "failed.json"
    _write_go_events(
        failed,
        [
            {"Action": "fail", "Package": "autonomy", "Test": "TestBroken"},
            {"Action": "fail", "Package": "autonomy"},
        ],
    )
    failed_receipt = verify_go_test_json(
        failed,
        tmp_path / "failed-receipt.json",
        go_test_exit_code=1,
        commit_sha="0" * 40,
        go_version="go1.23.4",
        race_enabled=True,
    )
    assert failed_receipt["conclusion"] == "FAILED"
    assert failed_receipt["failed"] == 1
    assert failed_receipt["packages_failed"] == 1

    malformed = tmp_path / "malformed.json"
    malformed.write_text("not-json\n", encoding="utf-8")
    malformed_receipt = verify_go_test_json(
        malformed,
        tmp_path / "malformed-receipt.json",
        go_test_exit_code=0,
        commit_sha="1" * 40,
        go_version="go1.23.4",
        race_enabled=True,
    )
    assert malformed_receipt["conclusion"] == "FAILED"


def test_oversized_go_report_fails_closed(tmp_path: Path) -> None:
    report = tmp_path / "oversized.json"
    report.write_bytes(b" " * (MAX_GO_TEST_BYTES + 1))
    receipt = verify_go_test_json(
        report,
        tmp_path / "receipt.json",
        go_test_exit_code=0,
        commit_sha="2" * 40,
        go_version="go1.23.4",
        race_enabled=True,
    )
    assert receipt["conclusion"] == "FAILED"
    assert "exceeds" in receipt["reason"]


def test_readme_contract_accepts_ordered_portable_evidence(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(_valid_readme(), encoding="utf-8")
    assert verify_readme(readme) == ()


def test_readme_contract_rejects_order_paths_and_unsupported_claims(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(
            (
                *reversed(HEADINGS),
                *REQUIRED_EVIDENCE,
                *REQUIRED_BOUNDARY,
                "/home/operator/repo",
                "sub-millisecond latency",
            )
        ),
        encoding="utf-8",
    )
    errors = verify_readme(readme)
    assert "audience headings are out of order" in errors
    assert "README exposes a machine-local path" in errors
    assert any(error.startswith("README contains unsupported public claims") for error in errors)


def test_readme_contract_rejects_appended_operational_authority_claim(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        _valid_readme() + "This system controls a vehicle flight computer in production.\n",
        encoding="utf-8",
    )
    assert any(
        error.startswith("README contains contradictory authority claims")
        for error in verify_readme(readme)
    )


def test_headings_inside_code_fence_do_not_satisfy_contract(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(
            ("```markdown", *HEADINGS, "```", *REQUIRED_EVIDENCE, *REQUIRED_BOUNDARY)
        ),
        encoding="utf-8",
    )
    assert any(
        error.startswith("missing required audience headings") for error in verify_readme(readme)
    )
