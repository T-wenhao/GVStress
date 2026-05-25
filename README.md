# GVStress

GigE Vision stress testing and monitoring framework for validating camera
stream stability under load.

## Overview

GVStress combines the original CLI test runner with a lightweight Web
monitoring architecture. It can simulate GigE Vision camera traffic, inspect a
Device Under Test (DUT), run smoke/soak/baseline scenarios, expose GVStress
metrics, and browse generated reports.

It includes:

- **Fakecam workers** that generate synthetic GigE Vision streams using Aravis
- **DUT probes** for NIC statistics, system metrics, and stream health monitoring
- **Node service commands** for local health, capability, and status checks
- **Controller service** for persistent job records and a small HTTP API
- **Web monitoring UI** for node/task/report views and a Prometheus-compatible
  `/metrics` endpoint
- **Structured reporting** with run artifacts, summary reports, and verdict attribution
- **Deployment assets** for native/systemd operation and Docker Compose based
  Prometheus/Grafana monitoring
- **Remote DUT support** via SSH for realistic single-node and multi-node topologies

## Installation

```bash
pip install -e .
```

### Dependencies

- Python 3.10+
- Aravis library (for fakecam workers)
- ethtool (for preflight NIC checks)
- SSH access to DUT nodes (for remote scenarios)
- Linux pktgen access, root, or CAP_NET_ADMIN for pktgen hardware validation
- Docker Compose, Prometheus, Grafana, and node_exporter for the optional
  monitoring stack

Development quality tools such as `ruff` and `mypy` are optional dev
dependencies. Install them in an isolated environment rather than in the system
Python environment.

## Quick Start

### 1. Verify Local Services

Check that the package and local node commands work:

```bash
python -m gvstress --help
python -m gvstress node health --json
python -m gvstress node capabilities --json
```

### 2. Configure Fakecam

Define fake camera configuration:

```bash
python -m gvstress fakecam up --config examples/fakecam_4p.yaml
```

Check status:

```bash
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json
```

### 3. Verify DUT Readiness

Run preflight inspection:

```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin
```

### 4. Run Test Scenarios

Smoke test (quick validation):

```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

Soak test (extended stability):

```bash
python -m gvstress test soak --config examples/scenario_soak.yaml
```

### 5. View Reports

Latest run report:

```bash
python -m gvstress report show --latest --source artifacts/smoke/runs
```

Export run data:

```bash
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output exported-run.json
```

### 6. Run the Local Controller and Web UI

Start the lightweight controller API:

```bash
python -m gvstress controller serve --host localhost --port 8079 --data-dir data
```

Start the Web monitoring UI:

```bash
python -m gvstress web serve \
    --host localhost \
    --port 8080 \
    --data-dir data \
    --artifacts-dir artifacts \
    --web-dir web
```

Useful local endpoints:

- `http://localhost:8079/health`
- `http://localhost:8079/api/jobs`
- `http://localhost:8080/`
- `http://localhost:8080/api/nodes`
- `http://localhost:8080/api/tasks`
- `http://localhost:8080/api/reports`
- `http://localhost:8080/metrics`

## CLI Entry Points

| Command | Purpose |
|---|---|
| `gvstress fakecam` | Manage fake camera workers |
| `gvstress dut` | Inspect DUT readiness over SSH |
| `gvstress test` | Run smoke, soak, four-stream, and loss-injection scenarios |
| `gvstress report` | Show and export structured run reports |
| `gvstress baseline` | Run pktgen baseline benchmarks |
| `gvstress dut-agent` | Remote DUT helper commands |
| `gvstress node` | Local node health, capability, and status commands |
| `gvstress controller` | Controller HTTP API service |
| `gvstress web` | Web monitoring UI service |

## Artifact Layout

```text
artifacts/
├── <scenario-name>/     # Scenario outputs (e.g., smoke, soak)
│   ├── preflight/       # Preflight check results
│   ├── fakecam/         # Fakecam state (if applicable)
│   └── runs/
│       └── <run-id>/
│           ├── raw/      # JSON Lines samples
│           ├── reports/  # run.json, summary.md
│           └── logs/     # Worker logs
└── pktgen/              # Baseline benchmarks
```

The controller stores job state under `data/`. The Web UI scans the configured
`artifacts/` tree for report browsing.

## Deployment Modes

GVStress separates the control plane from the data plane:

| Mode | Data Plane | Control Plane | Use Case |
|---|---|---|---|
| Full native | Native/systemd | Native | Hardware validation and benchmarking |
| Hybrid | Native remote nodes | Docker Compose or native control | Monitoring stack with bare-metal traffic |
| Full Compose | Containers | Docker Compose | UI/API development and demos only |

For performance-sensitive pktgen traffic, avoid Docker bridge networking. Use
native/systemd services or host-network privileged containers only where the
operator guide says they are appropriate.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success/pass |
| 1 | Usage/operational error |
| 2 | Warn |
| 3 | Fail |
| 4 | Not applicable/invalid |

## Documentation

### Product and Operation

- [Testing Guide](docs/testing.md)
- [Deployment Guide](docs/deployment.md)
- [Deployment Architecture ADR](docs/deployment-architecture.md)
- [Web Monitoring Operator Guide](docs/web-monitoring-operator-guide.md)
- [Prometheus Metrics Contract](docs/metrics-contract.md)
- [Migration from Ad Hoc Soak Test Script](docs/migration-from-soak-test.md)
- [Validation TODOs](docs/web-monitoring-validation-todos.md)

### 中文 (Chinese)

- [项目概览](README-zh.md)
- [快速入门指南](docs/quickstart-zh.md)
- [CLI 命令参考](docs/cli-reference-zh.md)
- [测试指南](docs/testing-zh.md)
- [部署指南](docs/deployment-zh.md)
- [部署架构决策](docs/deployment-architecture-zh.md)
- [Web 监控操作指南](docs/web-monitoring-operator-guide-zh.md)
- [Prometheus 指标合同](docs/metrics-contract-zh.md)
- [文档索引](docs/INDEX.md)

## License

MIT License
