from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

HEADINGS: Final = (
    "## For recruiters and non-technical reviewers",
    "## For senior engineers and domain experts",
    "## For AI systems and toolchains",
)
REQUIRED_EVIDENCE: Final = (
    ".github/workflows/ci.yml",
    "scripts/verify_junit.py",
    "go/autonomy/fsm_test.go",
    "glaciereq.spacex-autonomy.simulation-snapshot.v1",
    "blocked_scope:",
    "unverified_scope:",
    "relationships:",
)
REQUIRED_BOUNDARY: Final = (
    "This is an independent portfolio project",
    "does not claim SpaceX employment, endorsement, affiliation",
    "It does not contact a vehicle, network, provider, or external control system",
    "Simulation output is not operational flight guidance",
)
FORBIDDEN_CLAIMS: Final = (
    "sub-millisecond latency",
    "sub-100μs",
    "flight-certified",
    "flight certified",
    "provable termination guarantees",
    "no heap allocation in the hot path",
    "Byzantine fault-tolerant",
    "MCP Tool Exposure",
)
# These expressions are evaluated only on visible lines that are not explicit
# negations/limitations. They prevent an appended affirmative operational claim
# from coexisting with the repository's required non-flight boundary language.
FORBIDDEN_AFFIRMATIVE_PATTERNS: Final = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:controls?|commands?)\b.{0,40}\b(?:vehicle|actuator|flight computer)\b",
        r"\boperational\b.{0,30}\b(?:flight|launch|re-entry|reentry|landing|abort)\b",
        r"\bproduction deployment\b",
        r"\bSpaceX\b.{0,30}\b(?:internal|proprietary|production)\b",
        r"\bflight[- ](?:ready|proven|validated)\b",
        r"\bvalidated mission thresholds?\b",
    )
)
NEGATION_MARKERS: Final = (
    " no ",
    " not ",
    "does not",
    "do not",
    "is not",
    "are not",
    "cannot",
    "without",
    "unverified",
    "blocked",
    "limitation",
)
LOCAL_PATH = re.compile(
    r"file:///|/Users/|[A-Za-z]:\\Users\\|/(?:home|root|tmp|var|private|mnt)/[^\s)`\]}>]+|(?<![A-Za-z0-9_])~/",
    re.IGNORECASE,
)
FENCE_PATTERN = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _visible_lines(text: str) -> Iterator[tuple[int, str]]:
    fence_character: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines()):
        match = FENCE_PATTERN.match(line)
        if match:
            marker = match.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue
        if fence_character is None:
            yield line_number, line


def _is_explicit_boundary_line(line: str) -> bool:
    normalized = f" {line.strip().casefold()} "
    return any(marker in normalized for marker in NEGATION_MARKERS)


def _contradictory_claims(text: str) -> tuple[str, ...]:
    findings: list[str] = []
    for line_number, line in _visible_lines(text):
        if _is_explicit_boundary_line(line):
            continue
        for pattern in FORBIDDEN_AFFIRMATIVE_PATTERNS:
            if pattern.search(line):
                findings.append(f"line {line_number + 1}: {line.strip()}")
                break
    return tuple(findings)


def verify_readme(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    positions: dict[str, list[int]] = {heading: [] for heading in HEADINGS}

    for line_number, line in _visible_lines(text):
        for heading in HEADINGS:
            if line.strip() == heading:
                positions[heading].append(line_number)

    missing = [heading for heading, matches in positions.items() if not matches]
    duplicates = [heading for heading, matches in positions.items() if len(matches) > 1]
    if missing:
        errors.append(f"missing required audience headings: {missing}")
    if duplicates:
        errors.append(f"duplicate required audience headings: {duplicates}")
    if not missing and not duplicates:
        observed = [positions[heading][0] for heading in HEADINGS]
        if observed != sorted(observed):
            errors.append("audience headings are out of order")

    if LOCAL_PATH.search(text):
        errors.append("README exposes a machine-local path")

    absent_evidence = [value for value in REQUIRED_EVIDENCE if value not in text]
    if absent_evidence:
        errors.append(f"machine contract is incomplete: {absent_evidence}")

    absent_boundary = [value for value in REQUIRED_BOUNDARY if value not in text]
    if absent_boundary:
        errors.append(f"public authority boundary is incomplete: {absent_boundary}")

    visible_text = "\n".join(line for _, line in _visible_lines(text)).casefold()
    forbidden = [claim for claim in FORBIDDEN_CLAIMS if claim.casefold() in visible_text]
    if forbidden:
        errors.append(f"README contains unsupported public claims: {forbidden}")

    contradictions = _contradictory_claims(text)
    if contradictions:
        errors.append(f"README contains contradictory authority claims: {list(contradictions)}")
    return tuple(errors)


def resolve_readme() -> Path:
    repository = Path(__file__).resolve().parents[1] / "README.md"
    if repository.is_file():
        return repository
    packaged = Path(__file__).resolve().with_name("README.md")
    if packaged.is_file():
        return packaged
    raise FileNotFoundError("README.md is unavailable")


def main() -> int:
    errors = verify_readme(resolve_readme())
    if errors:
        raise SystemExit("README contract failed: " + "; ".join(errors))
    print("SpaceX Autonomy README contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
