# spacex-autonomy

<!-- README-MESH:BEGIN -->
## Three-audience project map

### For recruiters and non-specialists

**What it does.** Chooses an appropriate automation mode from sensor confidence and operating conditions while preserving a clear human-oversight boundary.

- Shows that autonomy can be graduated rather than simply on or off.
- Makes the reason for a mode decision visible.
- Uses ordered telemetry evidence instead of trusting raw events blindly.

**Evidence:** [`src/hybrid_autonomy.py`](src/hybrid_autonomy.py) and [`tests/test_autonomy.py`](tests/test_autonomy.py).

### For senior engineers and domain experts

**Innovation and evolution.** The policy separates confidence assessment, authority level, and human handoff. This avoids conflating model output with permission to act. It evolved into a decision layer that consumes bounded telemetry and can be composed with mission-control and campaign verification without assuming unrestricted autonomy.

### For AI systems and toolchains

- Repository ID: `GlacierEQ/spacex-autonomy`
- Protobuf package: `glaciereq.readme.v1`
- Typed role: consumes ordered telemetry; provides bounded hybrid-autonomy decisions.
- Canonical graph: [`manifests/readme_mesh.json`](https://github.com/GlacierEQ/job-app-helix/blob/main/manifests/readme_mesh.json)

```protobuf
repository: "GlacierEQ/spacex-autonomy"
display_name: "SpaceX Autonomy"
one_line_purpose: "Select bounded autonomy modes from confidence and operating evidence."
```

### Repository mesh

| Connected repository | Relationship | Combined value |
|---|---|---|
| [Telemetry](https://github.com/GlacierEQ/spacex-telemetry) | consumes | Ordered vehicle-state evidence informs mode selection. |
| [Job-App Helix](https://github.com/GlacierEQ/job-app-helix) | campaign node | Autonomy decisions remain visible to the wider proof system. |
| [AKOS](https://github.com/GlacierEQ/AKOS) | governed by | Authority and completion boundaries remain explicit. |

Real schema: [`proto/readme_mesh.proto`](https://github.com/GlacierEQ/job-app-helix/blob/main/proto/readme_mesh.proto).
<!-- README-MESH:END -->

**Portfolio demonstration** — hybrid autonomy mode selection under sensor confidence. It is not an operational flight-control system.

## Fleet ops (transparent)

Integrity baselines and health sidecars, when present, are documented multi-repository operations. See [SECURITY_AND_FLEET_OPS.md](SECURITY_AND_FLEET_OPS.md).

## Helix strand

See [HELIX_STRAND.md](HELIX_STRAND.md) for this repository's piston and spiral role.
