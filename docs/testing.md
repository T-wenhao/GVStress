# Testing Guide

This guide covers running tests with GVStress and interpreting results.

## Test Types

GVStress supports multiple test scenarios:

| Scenario | Duration | Warmup | Cooldown | Purpose |
|----------|----------|--------|----------|---------|
| smoke | 60s | 10s | 5s | Quick validation |
| four_stream | 300s | 10s | 5s | Multi-stream stress |
| soak | 1800s | 10s | 5s | Long-term stability |
| loss_injection | 300s | 10s | 5s | Packet loss resilience |

## CLI Commands

### Fakecam Management

Start fake cameras:
```bash
python -m gvstress fakecam up --config examples/fakecam_4p.yaml
```

Check status:
```bash
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json
```

Stop fake cameras:
```bash
python -m gvstress fakecam down --config examples/fakecam_4p.yaml
```

### Running Tests

Smoke test (quick validation):
```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

Four-stream stress test:
```bash
python -m gvstress test four-stream --config examples/scenario_4stream.yaml
```

Soak test (extended run):
```bash
python -m gvstress test soak --config examples/scenario_soak.yaml
```

Loss injection test:
```bash
python -m gvstress test loss-injection --config examples/scenario_loss.yaml
```

### Baseline Benchmarks

Run pktgen baseline:
```bash
python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml
```

### DUT Inspection

Check DUT readiness:
```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin
```

### Node and Web Monitoring

Check local node health and capabilities before running service-level or
hardware validation:

```bash
python -m gvstress node health --json
python -m gvstress node capabilities --json
python -m gvstress node status --json
```

Start the lightweight controller API:

```bash
python -m gvstress controller serve --host localhost --port 8079 --data-dir data
```

Start the Web monitoring UI in another terminal:

```bash
python -m gvstress web serve \
    --host localhost \
    --port 8080 \
    --data-dir data \
    --artifacts-dir artifacts \
    --web-dir web
```

Useful checks:

```bash
curl http://localhost:8079/health
curl http://localhost:8080/api/nodes
curl http://localhost:8080/api/reports
curl http://localhost:8080/metrics
```

### Reports

Report commands read from an artifact root. Scenario runs are stored under `<output>/<scenario-name>/runs/<run-id>/`.

View latest run report from a scenario run output:
```bash
python -m gvstress report show --latest --source artifacts/smoke/runs
```

View specific run:
```bash
python -m gvstress report show --run-id abc123 --source artifacts/smoke/runs
```

Export run report:
```bash
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output exported-run.json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success/pass |
| 1 | Usage/operational error |
| 2 | Warn |
| 3 | Fail |
| 4 | Not applicable/invalid |

## JSON Output

All commands support `--json` flag:

```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml --json
```

Output:
```json
{
  "run_id": "abc123",
  "scenario": "smoke",
  "run_validity": "valid",
  "aborted": false,
  "sample_counts": {
    "nic": 60,
    "stream": 60,
    "system": 60,
    "events": 5
  },
  "artifacts_root": "artifacts/smoke/runs/abc123"
}
```

## Artifact Interpretation

### Run Report (run.json)

Key fields:
- `verdict`: pass, warn, fail, not_applicable
- `run_validity`: valid, invalid_environment, invalid_prereq, interrupted
- `primary_attribution`: nic, stream, mixed, environment, unknown
- `samples`: paths to raw data files

### Summary Report (summary.md)

Human-readable markdown with:
- Run metadata (ID, timestamp, scenario)
- Preflight check results
- Sample counts
- Verdict and attribution
- Recommended actions

### Raw Samples

JSON Lines files in `raw/` directory:
- `nic_samples.jsonl`: NIC statistics per sample interval
- `stream_samples.jsonl`: Stream probe records
- `system_samples.jsonl`: System metrics (CPU, memory)
- `events_samples.jsonl`: State transitions and events

### Sample Record Structure

NIC sample:
```json
{
  "record_type": "nic_sample",
  "timestamp": 1234567890.123,
  "interface": "eno1",
  "rx_packets": 1000000,
  "rx_errors": 0,
  "rx_dropped": 0
}
```

Stream sample:
```json
{
  "record_type": "stream_sample",
  "timestamp": 1234567890.123,
  "serial": "GV-001",
  "ip": "192.168.10.11",
  "frames_received": 5000,
  "frames_lost": 0,
  "resend_requests": 10
}
```

## Analyzing Results

### Pass Conditions

- `run_validity=valid`
- `verdict=pass`
- All preflight checks passed
- No stream errors during test

### Warning Conditions

- `verdict=warn`
- Minor issues detected (e.g., occasional packet retries)
- Non-critical preflight warnings

### Fail Conditions

- `verdict=fail`
- `run_validity` is not valid
- Stream errors exceed threshold
- Dropped packets or frames

### Interpreting Attribution

- `nic`: Fault in network interface (driver, hardware)
- `stream`: Fault in stream handling (Aravis, resend logic)
- `mixed`: Multiple domains affected
- `environment`: Setup/configuration issues
- `unknown`: Unable to determine

## Recommended Actions

Based on attribution:

**NIC faults:**
- Update NIC driver/firmware
- Check cable quality
- Verify MTU settings
- Increase socket buffer sizes

**Stream faults:**
- Adjust packet timeout settings
- Tune resend request ratio
- Check receiver priority
- Verify GenICam configuration

**Environment faults:**
- Fix network topology
- Correct IP/interface mappings
- Verify SSH connectivity
- Install missing dependencies

## Best Practices

1. **Run preflight first**: Always verify setup before tests
2. **Start with smoke**: Quick validation before longer tests
3. **Use JSON for automation**: Parse results programmatically
4. **Archive artifacts**: Keep reports for trend analysis
5. **Monitor during soak**: Check intermediate status for long runs

## Troubleshooting

### Fakecam fails to start
- Check Aravis installation
- Verify interface names in config
- Ensure IP addresses are routable

### No stream samples
- Confirm fakecams are running
- Check firewall rules
- Verify GenICam files exist

### Preflight failures
- Review `reasons` in output
- Fix environment issues before testing
- Re-run preflight after changes

---

## 中文版本

本文档有中文版本：[测试指南 (中文)](testing-zh.md)
