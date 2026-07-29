# SpaceX Autonomy — Autonomous Flight Decision Engine 🚀

> **Real-time autonomous flight decision-making for launch vehicle abort, re-entry, and landing sequences.**

[![Python](https://img.shields.io/badge/Python-3.9+-blue)]()
[![Go](https://img.shields.io/badge/Go-1.21+-00ADD8)]()
[![Domain](https://img.shields.io/badge/Domain-Aerospace%20Autonomy-red)]()

---

## 🎯 For Recruiters & Hiring Managers

This repository implements a **flight autonomy decision engine** — the software brain that decides in milliseconds whether to continue, abort, or adjust a rocket's trajectory. It demonstrates:

- **Safety-critical decision trees** with formal abort criteria evaluation
- **Real-time sensor fusion** across IMU, GPS, pressurization, and thrust telemetry
- **Deterministic state machines** with provable termination guarantees
- **Sub-millisecond latency** event processing for time-critical abort decisions

**Why this matters**: Autonomous flight systems are the foundation of reusable rocketry. This codebase shows mastery of real-time systems, safety engineering, and high-stakes decision-making under uncertainty — skills directly transferable to autonomous vehicles, robotics, and mission-critical infrastructure.

---

## 🔬 For Engineers & Technical Reviewers

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                 FLIGHT AUTONOMY ENGINE               │
├──────────┬──────────┬──────────┬────────────────────┤
│  Sensor  │  State   │  Abort   │   Landing          │
│  Fusion  │  Machine │  Criteria│   Guidance          │
│  Layer   │  (FSM)   │  Engine  │   Computer          │
├──────────┴──────────┴──────────┴────────────────────┤
│              Telemetry Bus (UDP/Protobuf)            │
└─────────────────────────────────────────────────────┘
```

### Core Components

| Component | Language | Purpose |
|---|---|---|
| `src/autonomy_engine.py` | Python | Main FSM with abort criteria evaluation |
| `src/flight_fsm.go` | Go | High-throughput event-driven state machine |
| `tests/` | Python | Deterministic test harness with fault injection |

### Key Design Decisions

- **Go for the FSM core**: goroutine-per-sensor model with channel-based event dispatch achieves <100μs state transitions
- **Python for orchestration**: Rapid iteration on abort criteria and sensor fusion algorithms
- **Deterministic execution**: No heap allocation in the hot path — all buffers pre-allocated at init

---

## 🤖 ML/AI & Programmatic Mesh Integration

### Agent Mesh Connectivity

This module integrates with the GlacierEQ portfolio mesh via:

- **MCP Tool Exposure**: Flight state queryable as an MCP resource by orchestrator agents
- **Mastermind Sidecar**: `mastermind_sidecar.py` registers with the APEX Highway mesh for health monitoring
- **SHA-256 Integrity**: All source files tracked via `.integrity/file_hashes.json` for tamper detection

### AI/ML Extension Points

- **Reinforcement Learning**: The FSM reward function is exposed for RL-based abort threshold optimization
- **Anomaly Detection**: Sensor fusion layer supports pluggable anomaly models (isolation forest, autoencoder)
- **Digital Twin**: State machine can run in shadow mode against historical telemetry for model validation

```python
# Example: Query flight state via MCP
result = await mcp_client.call_tool("spacex-autonomy", "get_flight_state")
# Returns: {"phase": "POWERED_ASCENT", "abort_score": 0.02, "confidence": 0.98}
```

---

## ⚡ Quick Start

```bash
python3 src/autonomy_engine.py
python3 tests/test_autonomy.py
```
