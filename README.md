# GVStress

GigE Vision stress testing framework for validating camera stream stability under load.

## Overview

GVStress provides tools to simulate multiple GigE Vision cameras and stress test a Device Under Test (DUT) such as a frame grabber or vision system. It includes:

- **Fakecam workers** that generate synthetic GigE Vision streams using Aravis
- **DUT probes** for NIC statistics, system metrics, and stream health monitoring
- **Preflight checks** to validate environment readiness before test execution
- **Structured reporting** with run artifacts, summary reports, and verdict attribution
- **Remote DUT support** via SSH for realistic network topology testing

## Installation

```bash
pip install -e .
```

### Dependencies

- Python 3.10+
- Aravis library (for fakecam workers)
- ethtool (for preflight NIC checks)
- SSH access to DUT (for remote scenarios)

## Quick Start

### 1. Configure Fakecam

Define fake camera configuration:

```bash
python -m gvstress fakecam up --config examples/fakecam_4p.yaml
```

Check status:

```bash
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json
```

### 2. Verify DUT Readiness

Run preflight inspection:

```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin
```

### 3. Run Test Scenarios

Smoke test (quick validation):

```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

Soak test (extended stability):

```bash
python -m gvstress test soak --config examples/scenario_soak.yaml
```

### 4. View Reports

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

## Artifact Layout

```
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

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success/pass |
| 1 | Usage/operational error |
| 2 | Warn |
| 3 | Fail |
| 4 | Not applicable/invalid |

## Documentation

### English
- [Testing Guide](docs/testing.md)
- [Deployment Guide](docs/deployment.md)

### 中文 (Chinese)
- [项目概览 (README-zh.md)](README-zh.md)
- [快速入门指南](docs/quickstart-zh.md)
- [CLI 命令参考](docs/cli-reference-zh.md)
- [测试指南](docs/testing-zh.md)
- [部署指南](docs/deployment-zh.md)
- [文档索引](docs/INDEX.md)

## License

MIT License
