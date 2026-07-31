from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from defusedxml import ElementTree as SafeET

SCHEMA: Final = "glaciereq.spacex-autonomy.python-test-receipt.v1"
MAX_JUNIT_BYTES: Final = 5 * 1024 * 1024
FORBIDDEN_XML_MARKERS: Final = (b"<!DOCTYPE", b"<!ENTITY")


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


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        if size > MAX_JUNIT_BYTES:
            raise ValueError(f"JUnit report exceeds {MAX_JUNIT_BYTES} bytes")
        data = handle.read(MAX_JUNIT_BYTES + 1)
    if len(data) > MAX_JUNIT_BYTES:
        raise ValueError(f"JUnit report exceeds {MAX_JUNIT_BYTES} bytes")
    if len(data) != size:
        raise ValueError("JUnit report changed during verification")
    lowered = data.lower()
    if any(marker.lower() in lowered for marker in FORBIDDEN_XML_MARKERS):
        raise ValueError("JUnit report contains a forbidden DTD or entity declaration")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("JUnit report must use UTF-8 encoding") from exc
    return data


def _counts(root: Any) -> dict[str, int]:
    testcases = list(root.iter("testcase"))
    failures = sum(case.find("failure") is not None for case in testcases)
    errors = sum(case.find("error") is not None for case in testcases)
    skipped = sum(case.find("skipped") is not None for case in testcases)
    tests = len(testcases)
    return {
        "tests": tests,
        "executed": tests - skipped,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
    }


def verify_junit(
    junit_path: Path,
    output_path: Path,
    *,
    pytest_exit_code: int,
    commit_sha: str,
    python_version: str,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "commit_sha": commit_sha,
        "python_version": python_version,
        "pytest_exit_code": pytest_exit_code,
        "conclusion": "FAILED",
        "evidence_level": "NONE",
    }
    try:
        data = _read_bounded(junit_path)
        root = SafeET.fromstring(
            data,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
        counts = _counts(root)
        receipt.update(counts)
        receipt["junit_sha256"] = hashlib.sha256(data).hexdigest()

        if pytest_exit_code == 0 and counts["executed"] > 0:
            if counts["failures"] == 0 and counts["errors"] == 0:
                receipt["conclusion"] = "VERIFIED"
                receipt["evidence_level"] = "TEST"
            else:
                receipt["reason"] = "JUnit records failing or errored testcases"
        elif pytest_exit_code == 0:
            receipt["conclusion"] = "UNVERIFIED_ZERO_PROOF"
            receipt["reason"] = "zero executed tests cannot establish TEST evidence"
        else:
            receipt["reason"] = "pytest returned a non-zero exit code"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        receipt["reason"] = str(exc)

    _atomic_write(output_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a bounded TEST receipt from JUnit XML")
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pytest-exit-code", type=int, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--python-version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    namespace = build_parser().parse_args(argv)
    receipt = verify_junit(
        namespace.junit,
        namespace.output,
        pytest_exit_code=namespace.pytest_exit_code,
        commit_sha=namespace.commit_sha,
        python_version=namespace.python_version,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["conclusion"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
