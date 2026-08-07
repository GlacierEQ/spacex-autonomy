from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

SCHEMA: Final = "glaciereq.spacex-autonomy.go-test-receipt.v1"
MAX_GO_TEST_BYTES: Final = 10 * 1024 * 1024


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def verify_go_test_json(
    report_path: Path,
    output_path: Path,
    *,
    go_test_exit_code: int,
    commit_sha: str,
    go_version: str,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "commit_sha": commit_sha,
        "go_version": go_version,
        "go_test_exit_code": go_test_exit_code,
        "conclusion": "FAILED",
        "evidence_level": "NONE",
    }
    try:
        size = report_path.stat().st_size
        if size > MAX_GO_TEST_BYTES:
            raise ValueError(f"Go test report exceeds {MAX_GO_TEST_BYTES} bytes")
        data = report_path.read_bytes()
        if len(data) != size:
            raise ValueError("Go test report changed during verification")
        text = data.decode("utf-8")

        passed = 0
        failed = 0
        skipped = 0
        packages_failed = 0
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            event = json.loads(line)
            action = event.get("Action")
            test_name = event.get("Test")
            if test_name:
                if action == "pass":
                    passed += 1
                elif action == "fail":
                    failed += 1
                elif action == "skip":
                    skipped += 1
            elif action == "fail" and event.get("Package"):
                packages_failed += 1
            if not isinstance(event, dict):
                raise ValueError(f"line {line_number} is not an object")

        receipt.update(
            {
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "executed": passed + failed,
                "packages_failed": packages_failed,
                "report_sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        if go_test_exit_code == 0 and passed > 0 and failed == 0 and packages_failed == 0:
            receipt["conclusion"] = "VERIFIED"
            receipt["evidence_level"] = "TEST"
        elif go_test_exit_code == 0 and passed == 0:
            receipt["conclusion"] = "UNVERIFIED_ZERO_PROOF"
            receipt["reason"] = "zero passed Go tests cannot establish TEST evidence"
        else:
            receipt["reason"] = "Go test execution or event stream contains failures"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        receipt["reason"] = str(exc)

    _atomic_write(output_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a TEST receipt from go test -json")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--go-test-exit-code", type=int, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--go-version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    namespace = build_parser().parse_args(argv)
    receipt = verify_go_test_json(
        namespace.report,
        namespace.output,
        go_test_exit_code=namespace.go_test_exit_code,
        commit_sha=namespace.commit_sha,
        go_version=namespace.go_version,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["conclusion"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
