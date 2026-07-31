"""Repository-local health report for the autonomy simulation toolkit.

This sidecar does not register with an external control plane. It reports only
local file presence, SHA-256 values, and process uptime.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Final

MODULE_PATHS: Final = (
    Path("src/spacex_autonomy/simulation.py"),
    Path("src/spacex_autonomy/estimation.py"),
    Path("src/spacex_autonomy/control.py"),
    Path("src/spacex_autonomy/consensus.py"),
    Path("src/hybrid_autonomy.py"),
    Path("go/autonomy/fsm.go"),
)


class MastermindSidecar:
    """Produce a bounded local repository health report."""

    def __init__(
        self,
        repo_name: str = "spacex-autonomy",
        repository_root: Path | None = None,
    ) -> None:
        self.repo_name = repo_name
        self.repository_root = repository_root or Path(__file__).resolve().parent
        self.start_time = time.monotonic()

    def file_hash(self, relative_path: Path) -> str:
        path = self.repository_root / relative_path
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def module_evidence(self) -> dict[str, dict[str, object]]:
        evidence: dict[str, dict[str, object]] = {}
        for relative_path in MODULE_PATHS:
            path = self.repository_root / relative_path
            evidence[relative_path.as_posix()] = {
                "present": path.is_file(),
                "sha256": self.file_hash(relative_path) if path.is_file() else None,
            }
        return evidence

    def health_report(self) -> dict[str, object]:
        evidence = self.module_evidence()
        present = sum(bool(item["present"]) for item in evidence.values())
        status = "healthy" if present == len(evidence) else "degraded"
        return {
            "schema": "glaciereq.repository-local-health.v1",
            "repo": self.repo_name,
            "uptime_seconds": round(time.monotonic() - self.start_time, 6),
            "status": status,
            "modules_present": present,
            "modules_expected": len(evidence),
            "module_evidence": evidence,
            "external_registration_verified": False,
        }

    def status(self) -> str:
        return json.dumps(self.health_report(), indent=2, sort_keys=True)


if __name__ == "__main__":
    print(MastermindSidecar().status())
