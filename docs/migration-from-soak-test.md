# Migration from Ad Hoc Soak Test Script

## Status

`soak_test.py` has been removed. All soak testing is now performed through
the GVStress CLI or the controller service.

## What Changed

| Before (ad hoc) | After (GVStress CLI) |
|---|---|
| `python soak_test.py` | `python -m gvstress test soak --config examples/scenario_soak.yaml` |
| Hardcoded config in script | YAML configuration under `examples/` |
| Manual artifact management | Structured output under `artifacts/soak/` |
| No preflight checks | Automatic preflight validation |
| No verdict attribution | Structured verdict (pass/warn/fail) |
| No JSON output | `--json` flag for machine-readable output |

## Command Mapping

### Run a soak test

```bash
# Old (removed)
python soak_test.py

# New
python -m gvstress test soak --config examples/scenario_soak.yaml
```

### Run with custom output directory

```bash
python -m gvstress test soak \
    --config examples/scenario_soak.yaml \
    --output /path/to/output
```

### Run with JSON output (for CI/automation)

```bash
python -m gvstress test soak \
    --config examples/scenario_soak.yaml \
    --json
```

### View reports

```bash
# Show latest run report
python -m gvstress report show --latest --source artifacts/soak/runs

# Export specific run
python -m gvstress report export \
    --run-id <run-id> \
    --source artifacts/soak/runs \
    --output exported-run.json
```

## Configuration

Soak test parameters are defined in `examples/scenario_soak.yaml`:

```yaml
scenarios:
  - name: soak
    duration: 1800    # 30 minutes
    warmup: 10        # seconds
    cooldown: 5       # seconds
```

Adjust `duration`, `warmup`, and `cooldown` to suit your test requirements.
Camera definitions, DUT interfaces, and stream settings are also configured
in the same YAML file.

## Web / Controller Alternative

For programmatic or remote job management, use the controller service:

### ControllerService (Python API)

```python
from pathlib import Path
from gvstress.controller import ControllerService, JobStatus

service = ControllerService(data_dir=Path("/var/lib/gvstress"))

# Create and track a soak job
job = service.create_job(name="soak-30min")
print(f"job_id={job.id}")  # e.g., "a1b2c3d4"

# Transition through lifecycle
service.start_job(job.id)
# ... run soak test via CLI or orchestrator ...
service.complete_job(job.id, result={"verdict": "pass"})
```

### TestJob Domain Model

The `gvstress.web.domain` module provides validated job state transitions:

```python
from gvstress.web.domain import TestJob, TestJobState, TestTopology, NodeRole

# Jobs enforce valid state transitions via Pydantic validators
# PENDING -> RUNNING -> STOPPING -> COMPLETED/FAILED
```

### REST API (planned)

The controller service is designed to back a REST API for:

- `POST /jobs` - Create a new soak test job
- `GET /jobs/{id}` - Query job status
- `POST /jobs/{id}/start` - Start execution
- `POST /jobs/{id}/complete` - Mark complete with results

## Artifact Layout

All soak test outputs are organized under `artifacts/soak/`:

```
artifacts/soak/
├── preflight/       # Environment validation results
├── fakecam/         # Fake camera state (if applicable)
└── runs/
    └── <run-id>/
        ├── raw/      # JSON Lines samples
        ├── reports/  # run.json, summary.md
        └── logs/     # Worker logs
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Soak test passed |
| 1 | Usage/operational error |
| 2 | Warning conditions detected |
| 3 | Soak test failed |
| 4 | Not applicable / invalid configuration |

## Security Notes

- No credentials are stored in configuration files
- SSH credentials for remote DUT access should be provided via environment
  variables or SSH key authentication
- Never commit IP addresses, hostnames, or credentials to version control
