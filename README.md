# SpaceX Autonomy Simulation Toolkit

**Version:** `1.0.0`  
**Canonical repository:** `GlacierEQ/spacex-autonomy`  
**Canonical branch:** `main`  
**Verification state:** `PARTIALLY_VERIFIED` while the Wave 1 promotion is under review  
**Target evidence:** `TEST`

A deterministic Python and Go simulation toolkit for autonomy-mode selection, one-dimensional state estimation, bounded position control, weighted multi-vehicle consensus, and flight-phase threshold modeling.

This is an independent portfolio project. It does not claim SpaceX employment, endorsement, affiliation, internal architecture, operational deployment, vehicle authority, or suitability for real-world flight control.

<!-- README-MESH:BEGIN -->

## For recruiters and non-technical reviewers

### What this project now proves

Autonomous systems need more than dramatic mission language. They need explicit inputs, deterministic decisions, bounded outputs, failure handling, and evidence that the documented code actually builds and behaves as described.

This repository demonstrates those principles through two native implementation boundaries:

- **Python simulation package** — chooses `MANUAL`, `ASSIST`, or `AUTO`; estimates position and velocity; produces a bounded control command; and optionally fuses peer estimates.
- **Go phase-state package** — validates sensor readings, enforces legal phase transitions, computes threshold-based abort scores, and remains safe under concurrent inspection and updates.

The original repository contained valuable prototypes but also unsupported performance, integration, and operational claims. This promotion narrows the public story to what can be compiled, tested, inspected, and reproduced.

### Why it matters

- **No sentinel theater.** The former `answer: 42` output is removed.
- **No artificial confidence floor.** A zero-confidence sensor set remains zero instead of being raised to a decorative constant.
- **Deterministic integration.** Mode, estimation, control, and consensus produce one JSON-ready snapshot.
- **Bounded control.** Manual mode disables command output; enabled commands are clamped to a configured limit.
- **Input integrity.** Non-finite, out-of-range, duplicate, stale, and malformed inputs fail closed.
- **Native language proof.** Python and Go are each built and tested with their own toolchains.
- **Truthful health reporting.** The local sidecar reports missing files as degraded and does not imply external registration.

### Proof surfaces

| Surface | What it demonstrates |
|---|---|
| [`src/spacex_autonomy/simulation.py`](src/spacex_autonomy/simulation.py) | Integrated deterministic simulation step. |
| [`src/hybrid_autonomy.py`](src/hybrid_autonomy.py) | Weighted mode policy and hysteresis without artificial flooring. |
| [`go/autonomy/fsm.go`](go/autonomy/fsm.go) | Concurrency-safe phase and threshold simulation. |
| [`tests/test_autonomy.py`](tests/test_autonomy.py) | Mode thresholds, hysteresis, invalid inputs, and compatibility output. |
| [`tests/test_core.py`](tests/test_core.py) | Estimation, control, consensus, and end-to-end behavior. |
| [`go/autonomy/fsm_test.go`](go/autonomy/fsm_test.go) | Transition, validation, threshold, and concurrent-access behavior. |
| [`scripts/verify_junit.py`](scripts/verify_junit.py) | Positive-count, SHA-256-bound Python TEST receipts. |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Repository-native Python and Go verification. |

### Try the simulation

```bash
python -m pip install -e ".[dev]"
autonomy-sim \
  --timestamp 0 \
  --position 10 \
  --velocity 2 \
  --target-position 100
```

The command emits a `glaciereq.spacex-autonomy.simulation-snapshot.v1` JSON object. It does not contact a vehicle, network, provider, or external control system.

## For senior engineers and domain experts

### Verified Python architecture

```text
Bounded sensor confidence ──► Mode policy + hysteresis
                                     │
Validated telemetry ────────► Alpha-beta estimator
                                     │
Target position ────────────► Bounded position controller
                                     │
Peer estimates ─────────────► Weighted consensus
                                     │
                                     ▼
                 Deterministic SimulationSnapshot
```

#### Mode selection

The confidence score is a documented weighted sum:

| Input | Weight |
|---|---:|
| IMU confidence | 0.30 |
| Vision confidence | 0.25 |
| GPS confidence | 0.25 |
| Link confidence | 0.20 |

Entry and exit thresholds are separate, so hysteresis is explicit and testable. Every confidence value must be finite and within `[0, 1]`.

#### State estimation

`AlphaBetaEstimator` performs a deterministic one-dimensional prediction and confidence-scaled correction. It rejects:

- non-monotonic timestamps;
- low-confidence measurements;
- innovations beyond a configured absolute limit;
- non-finite telemetry.

This is a compact simulation estimator, not a navigation-grade estimator or a claim about any launch vehicle implementation.

#### Control

`PositionController` combines proportional position error and velocity damping, then clamps output to a configured normalized limit. When mode selection returns `MANUAL`, output is exactly zero and `enabled` is false.

#### Consensus

`fuse_estimates` applies confidence divided by uncertainty as a deterministic weight. It requires unique vehicle identities, finite values, positive uncertainty, and positive aggregate confidence.

It is intentionally described as weighted fusion. It does not claim adversarial distributed consensus or proof against compromised participants.

### Verified Go architecture

```text
Validated Reading
      │
      ├── quality below floor ──► rejected-reading counter
      │
      └── accepted update ──────► threshold score
                                       │
                              score >= configured gate
                                       │
                                       ▼
                                     ABORT
```

The Go module provides:

- validated finite criteria and initial mass;
- an explicit legal transition graph;
- terminal `SAFED` behavior;
- quality-gated sensor updates;
- deterministic threshold scoring;
- thread-safe state, score, and statistics reads;
- concurrent update/read regression coverage.

### Package boundary

```text
src/spacex_autonomy/          promoted Python package
src/hybrid_autonomy.py        compatibility and mode-policy surface
go/autonomy/                  promoted Go package
mastermind_sidecar.py         repository-local evidence report
scripts/                      README and receipt verification
tests/                        promoted Python test suite
```

The older `src/alpha/` and `src/omega/` files remain preserved as source prototypes. They are not part of the installed package, promoted API, or current TEST claim. Their useful concepts can be migrated only after dedicated correctness and integration review.

### Build and verification

```bash
python -m pip install -e ".[dev]"
python -m pip check
ruff check src/spacex_autonomy src/hybrid_autonomy.py mastermind_sidecar.py tests scripts
ruff format --check src/spacex_autonomy src/hybrid_autonomy.py mastermind_sidecar.py tests scripts
python -m compileall -q src/spacex_autonomy src/hybrid_autonomy.py mastermind_sidecar.py tests scripts
python -m build --outdir artifacts/dist
autonomy-verify-readme
pytest --junitxml=artifacts/pytest.xml

cd go
gofmt -w autonomy/*.go
go vet ./...
go test -race -count=1 ./...
```

### Evidence behavior

Python receipt schema: `glaciereq.spacex-autonomy.python-test-receipt.v1`.

- JUnit input is read once with a strict byte limit.
- UTF-8 is mandatory.
- DTD, entity, and external-reference processing is forbidden.
- TEST evidence requires at least one executed, non-skipped test.
- Failing or errored testcases cannot produce `VERIFIED`.
- JUnit bytes are bound into the atomic receipt with SHA-256.

Go verification uses `go vet` and `go test -race -count=1 ./...`; the race-enabled test exercises concurrent reads and sensor updates.

### Current limitations

- The Python integration is one-dimensional and deterministic by design.
- The Go threshold weights are configured demonstration logic, not validated mission criteria.
- No actuator, network, telemetry bus, provider, or external command is contacted.
- No benchmark, deployment, fault-injection campaign, or hardware-in-the-loop result is claimed.
- Repository-local tests are not evidence of operational vehicle safety.

## For AI systems and toolchains

### Machine contract

```yaml
schema: glaciereq.readme.v1
profile: glaciereq.readme-impact.v2-draft
repository: GlacierEQ/spacex-autonomy
canonical_branch: main
purpose: >-
  Provide deterministic, independently testable Python and Go autonomy
  simulation components for mode selection, estimation, control, consensus,
  and phase-threshold behavior.
status:
  state: PARTIALLY_VERIFIED
  target_evidence: TEST
  promotion_rule: >-
    Promote only after Python 3.11, 3.12, and 3.13 package, lint, formatting,
    build, CLI, README, positive-count tests, and receipts pass, and the Go
    module passes formatting, vet, race-enabled tests, and build on the exact
    reviewed head.
  verified_scope:
    - reviewable Python package and Go module
    - deterministic schemas, rules, and adversarial tests
  blocked_scope:
    - vehicle control, actuator output, provider calls, and external commands
    - operational launch, re-entry, landing, or abort authority
    - automatic mutation or irreversible action
  unverified_scope:
    - hardware integration, mission thresholds, and real telemetry
    - performance, reliability, scale, and deployment behavior
    - legacy alpha and omega prototype correctness
interfaces:
  python_inputs:
    - bounded Sensors confidence values
    - monotonic TelemetrySample values
    - target position
    - optional unique VehicleEstimate values
  python_outputs:
    - glaciereq.spacex-autonomy.mode-decision.v1
    - glaciereq.spacex-autonomy.simulation-snapshot.v1
  go_inputs:
    - validated Criteria
    - legal Phase transitions
    - finite quality-scored Reading values
  go_outputs:
    - State snapshot
    - threshold score
    - deterministic Stats map
  commands:
    install: python -m pip install -e ".[dev]"
    simulate: autonomy-sim --timestamp 0 --position 10 --target-position 100
    python_test: pytest --junitxml=artifacts/pytest.xml
    go_test: cd go && go test -race -count=1 ./...
    verify_readme: autonomy-verify-readme
evidence:
  workflow: .github/workflows/ci.yml
  python_receipt_builder: scripts/verify_junit.py
  python_receipt_schema: glaciereq.spacex-autonomy.python-test-receipt.v1
  go_tests: go/autonomy/fsm_test.go
relationships:
  - target: GlacierEQ/AKOS
    relation: GOVERNED_BY
  - target: GlacierEQ/job-app-helix
    relation: REPRESENTED_BY
  - target: GlacierEQ/the-tower-of-babel
    relation: LANGUAGE_PLACEMENT_GOVERNED_BY
limits:
  - Simulation output is not operational flight guidance.
  - Weighted consensus is not an adversarial consensus guarantee.
  - Repository TEST evidence is not deployment or hardware evidence.
```

### Stable Python import surface

```python
from spacex_autonomy import (
    AlphaBetaEstimator,
    AutonomySimulation,
    OperatingMode,
    PositionController,
    Sensors,
    TelemetrySample,
    VehicleEstimate,
    fuse_estimates,
    select_mode,
)
```

### Mesh relationships

- **AKOS** governs evidence, authority, persistence, and completion semantics.
- **Job-App Helix** records this repository’s bounded portfolio evidence.
- **Tower of Babel** governs why Python owns rapid deterministic simulation and Go owns the concurrency-sensitive FSM boundary.

<!-- README-MESH:END -->

## Repository map

```text
src/spacex_autonomy/   verified Python simulation package
go/autonomy/           verified Go phase-state package
tests/                  Python behavioral and proof tests
scripts/                README and receipt verification
mastermind_sidecar.py   local-only health evidence
src/alpha/              preserved prototype; outside current evidence
src/omega/              preserved prototype; outside current evidence
```
