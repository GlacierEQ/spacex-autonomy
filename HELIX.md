# HELIX Architecture — spacex-autonomy

## Double Helix Pattern

**Alpha (What)** — Pure physics models, stateless computation
- state_estimator

**Omega (How)** — Controllers, orchestration, stateful management  
- flight_controller,multi_vehicle_consensus

## Design Principles

- Zero external dependencies (stdlib only)
- Stateless alpha, stateful omega
- SHA-256 file integrity verification
- Shadow watchdog daemon monitoring
- Mastermind sidecar coordination

## Data Flow

```
Alpha Models → Omega Controllers → Mastermind Sidecar → Shadow Infrastructure
```
