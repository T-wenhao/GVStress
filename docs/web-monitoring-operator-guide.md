# Web Monitoring Operator Guide

This guide provides operators with comprehensive information for deploying, configuring, and monitoring GVStress in production environments.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Deployment Modes](#deployment-modes)
- [Metrics and Monitoring](#metrics-and-monitoring)
- [Test Strategy](#test-strategy)
- [Operational Procedures](#operational-procedures)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

GVStress is a GigE Vision stress testing framework designed to validate camera stream stability under load. The architecture separates concerns between data plane (traffic generation) and control plane (orchestration and monitoring).

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Control Plane                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   CLI Tool   │  │   Web API    │  │  Controller Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SSH / HTTP
                              │
┌─────────────────────────────────────────────────────────────────┐
│                        Data Plane                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Fakecam      │  │   DUT Agent  │  │   pktgen Worker      │  │
│  │ Workers      │  │   (SSH)      │  │   (Kernel)           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Purpose | Network Requirements |
|-----------|---------|---------------------|
| Fakecam Workers | Generate synthetic GigE Vision streams | Direct NIC access, static IPs |
| DUT Agent | Collect NIC stats, system metrics, stream health | SSH access from control host |
| pktgen Worker | Kernel-level packet generation | Root/CAP_NET_ADMIN, `/proc/net/pktgen` access |
| Controller Service | Job orchestration and lifecycle management | HTTP API endpoint |
| CLI Tool | Command-line interface for test execution | SSH to remote nodes |

## Deployment Modes

GVStress supports three deployment modes with different trade-offs between convenience and performance.

### Deployment Matrix

| Mode | Data Plane | Control Plane | Use Case | Performance |
|------|-----------|---------------|----------|-------------|
| **Full Native** | Native/systemd | Native | Production, benchmarking | Maximum |
| **Hybrid** | Native on remote nodes | Docker Compose | Containerized control, bare-metal data | High |
| **Full Compose** | Docker containers | Docker Compose | Development, demos | Limited |

### 1. Full Native Deployment (Recommended for Production)

All components run natively on bare metal or VMs with systemd service management.

**Single-Node Setup:**

```bash
# Install GVStress
pip install -e .

# Start fakecam workers
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# Run preflight checks
python -m gvstress dut inspect \
    --host localhost \
    --ifaces eno1,eno2,eno3,eno4 \
    --json

# Execute test
python -m gvstress test soak --config examples/scenario_soak.yaml
```

**Two-Node Setup:**

```bash
# Generator node - start fakecam
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# DUT node - configure SSH access
# Control host runs test with remote DUT
python -m gvstress test soak \
    --config examples/scenario_soak.yaml \
    --dut-host dut.example.com \
    --dut-user admin
```

### 2. Hybrid Deployment (Compose Control + Native Data Nodes)

Control plane services run in Docker Compose; generator/DUT nodes run natively.

**Control Plane (Docker Compose):**

```yaml
# docker-compose.yml
services:
  gvstress-controller:
    image: gvstress/controller:latest
    ports:
      - "8080:8080"
    volumes:
      - /var/lib/gvstress:/data
    environment:
      - DATA_DIR=/data
```

**Data Nodes (Native):**

```bash
# On generator nodes - run workers natively
sudo systemctl start gvstress-worker

# On DUT nodes - ensure SSH access and agent availability
python -m gvstress.cli.dut_agent ping
```

**Hybrid Command Example:**

```bash
# From control container, execute on native nodes via SSH
docker exec gvstress-controller \
    python -m gvstress test soak \
    --config /config/scenario_soak.yaml \
    --generator-host gen1.example.com \
    --dut-host dut1.example.com
```

### 3. Full Docker Compose (Development Only)

**WARNING:** Docker bridge networking introduces NAT, MTU changes, and packet overhead. Not suitable for performance-sensitive pktgen traffic.

```yaml
# docker-compose.yml - Development only
services:
  gvstress-worker:
    image: gvstress/worker:latest
    network_mode: host      # Required for NIC access
    privileged: true         # Required for /proc/net/pktgen
    volumes:
      - /proc/net/pktgen:/proc/net/pktgen
```

### Capability Requirements

| Component | Required Capabilities | Privileged Required |
|-----------|----------------------|---------------------|
| Fakecam workers | None | No |
| pktgen workers | CAP_NET_ADMIN or root | Yes (or cap_add) |
| DUT agent (SSH) | None | No |
| node_exporter | None | No |

## Metrics and Monitoring

### node_exporter vs GVStress Custom Metrics

GVStress uses a separation of concerns for metrics collection:

#### node_exporter (Infrastructure Metrics)

node_exporter provides standard Prometheus node metrics:

- **CPU**: Usage percentages, load averages
- **Memory**: Utilization, swap usage
- **Disk**: I/O rates, space usage
- **Network**: Interface statistics (packets, bytes, errors)
- **System**: Uptime, file descriptors

**Deployment:**

```bash
# Run as systemd service
sudo systemctl start prometheus-node-exporter

# Or as Docker container
docker run -d \
  --net="host" \
  --pid="host" \
  -v "/:/host:ro,rslave" \
  prom/node-exporter:latest \
  --path.rootfs=/host
```

**Scraping:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets: ['generator:9100', 'dut:9100']
```

#### GVStress Custom Metrics (Application Metrics)

GVStress exposes application-specific metrics:

- **Stream Health**: Frames received, frames lost, resend requests
- **Worker Status**: Active workers, camera states
- **Test Progress**: Sample counts, duration, verdict
- **NIC Statistics**: Per-interface packet counters (from DUT)
- **System Metrics**: CPU, memory during test (from DUT agent)

**Collection Method:**

GVStress metrics are collected via the reporting pipeline and stored in run artifacts:

```
artifacts/<scenario>/runs/<run-id>/
├── raw/
│   ├── nic_samples.jsonl       # NIC statistics per sample
│   ├── stream_samples.jsonl    # Stream probe records
│   ├── system_samples.jsonl    # System metrics
│   └── events_samples.jsonl    # State transitions
└── reports/
    ├── run.json                # Structured run report
    └── summary.md              # Human-readable summary
```

#### Key Differences

| Aspect | node_exporter | GVStress Custom Metrics |
|--------|--------------|------------------------|
| **Scope** | Infrastructure-wide | Test-specific |
| **Granularity** | System-level | Per-stream, per-interface |
| **Persistence** | Time-series DB (Prometheus) | Run artifacts (JSON Lines) |
| **Attribution** | Node-level | Test-run-level |
| **Collection** | Pull (scraping) | Push (during test) |
| **Lifespan** | Continuous | Test duration |

**Rationale for Separation:**

1. **Independent scaling**: node_exporter can be shared across multiple workloads
2. **Test attribution**: GVStress metrics remain tied to specific test runs
3. **Operational flexibility**: Infrastructure monitoring continues even when tests are not running

### Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                          │
├─────────────────────────────────────────────────────────────┤
│  Prometheus (node_exporter)    │   GVStress Artifacts       │
│  - Continuous collection       │   - Per-test collection    │
│  - Long-term trends            │   - Run attribution        │
│  - Infrastructure health       │   - Stream-specific data   │
└─────────────────────────────────────────────────────────────┘
```

### Report Semantics

#### Run Report (run.json)

Key fields for operators:

| Field | Values | Description |
|-------|--------|-------------|
| `verdict` | pass, warn, fail, not_applicable | Overall test result |
| `run_validity` | valid, invalid_environment, invalid_prereq, interrupted | Whether results are trustworthy |
| `primary_attribution` | nic, stream, mixed, environment, unknown | Where the fault lies |
| `aborted` | true, false | Whether test was manually aborted |

#### Verdict Interpretation

- **pass**: Test completed successfully with no issues
- **warn**: Test completed with minor issues (e.g., occasional packet retries)
- **fail**: Test failed due to errors exceeding thresholds
- **not_applicable**: Configuration or environment invalid for test

#### Attribution Guide

| Attribution | Meaning | Action |
|-------------|---------|--------|
| `nic` | Network interface fault | Check driver/firmware, cables, MTU |
| `stream` | Stream handling fault | Tune Aravis settings, resend logic |
| `mixed` | Multiple domains affected | Comprehensive investigation needed |
| `environment` | Setup/configuration issue | Verify topology, SSH, dependencies |
| `unknown` | Unable to determine | Review logs, increase sampling |

### pktgen Limitations

**IMPORTANT:** pktgen provides baseline benchmarks but has important limitations:

1. **Not equivalent to GigE Vision**: pktgen generates raw packets, not GigE Vision protocol traffic
2. **No protocol overhead**: pktgen does not include GVSP (GigE Vision Streaming Protocol) headers
3. **No resend logic**: pktgen does not implement packet resend mechanisms
4. **Kernel-level only**: pktgen operates at kernel level, bypassing user-space processing

**Use pktgen for:**
- Raw throughput baseline measurements
- Network infrastructure validation
- Driver performance testing

**Do NOT use pktgen for:**
- GigE Vision protocol validation
- Application-level performance testing
- Stream stability assessment

### RX Background Traffic Warning

**CRITICAL:** RX (receive) packet counters may include background traffic not related to the test.

#### Why RX Increments May Include Background Traffic

1. **Broadcast/Multicast traffic**: ARP, LLDP, IPv6 neighbor discovery
2. **Management traffic**: SNMP, monitoring agents, SSH connections
3. **OS services**: NTP, DNS, system updates
4. **Other applications**: Co-located services on the DUT

#### Impact on Measurements

```
Observed RX = Test Traffic + Background Traffic
```

This means:
- **RX counters may be higher** than actual test traffic
- **Loss calculations** based on TX/RX differences may be inaccurate
- **Per-interface totals** include all received packets

#### Mitigation Strategies

1. **Use dedicated test interfaces**: Isolate test traffic on dedicated NICs
2. **Baseline measurement**: Measure background traffic before test
3. **Filter by protocol**: Where possible, filter GigE Vision traffic specifically
4. **Compare TX/RX**: Cross-reference generator TX with DUT RX

#### Example Background Traffic Estimation

```bash
# Measure background traffic before test
python -m gvstress dut inspect --host dut --ifaces eno1 --json
# Record rx_packets baseline

# Run test
python -m gvstress test smoke --config examples/scenario_smoke.yaml

# Compare delta vs expected test traffic
```

## Test Strategy

### Test Matrix

GVStress implements a comprehensive testing strategy across multiple levels:

| Test Level | Purpose | Tools | Frequency |
|------------|---------|-------|-----------|
| **Unit** | Component isolation | pytest | Every commit |
| **Integration** | Component interaction | pytest + fixtures | Every commit |
| **Service** | API contract validation | pytest + HTTP client | Pre-release |
| **Compose** | Container orchestration | docker-compose | Pre-release |
| **Hardware** | Physical NIC validation | Real hardware | Weekly |
| **Browser** | UI/UX validation | Playwright | Pre-release |

### Unit Tests

**Scope:** Individual functions, classes, and modules in isolation.

**Command:**

```bash
pytest tests/unit/ -v --cov=gvstress
```

**Coverage Areas:**
- Configuration parsing and validation
- Metric calculation functions
- State machine transitions
- Utility functions

### Integration Tests

**Scope:** Component interactions and data flow.

**Command:**

```bash
pytest tests/integration/ -v
```

**Coverage Areas:**
- Fakecam worker lifecycle
- DUT agent communication
- Report generation pipeline
- Artifact storage

### Service Tests

**Scope:** API contracts and service boundaries.

**Command:**

```bash
pytest tests/service/ -v
```

**Coverage Areas:**
- Controller service endpoints
- Job lifecycle management
- Topology validation
- State transition enforcement

### Compose Tests

**Scope:** Docker Compose orchestration.

**Command:**

```bash
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

**Coverage Areas:**
- Service startup and health checks
- Inter-service communication
- Volume mounting and permissions
- Network configuration

### Hardware Tests

**Scope:** Physical hardware validation.

**Requirements:**
- Physical generator and DUT machines
- Dedicated network interfaces
- Static IP configuration

**Command:**

```bash
# Full hardware validation suite
python -m gvstress test soak --config examples/scenario_soak.yaml

# Quick validation
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

**Coverage Areas:**
- Real NIC throughput
- Packet loss under load
- Driver stability
- Hardware timestamp accuracy

### Browser Tests

**Scope:** Web UI validation.

**Command:**

```bash
pytest tests/browser/ -v --headed
```

**Coverage Areas:**
- Dashboard rendering
- Job status display
- Report visualization
- User interactions

### Test Configuration Examples

#### Smoke Test (Quick Validation)

```yaml
# examples/scenario_smoke.yaml
scenarios:
  - name: smoke
    duration: 60      # 1 minute
    warmup: 10
    cooldown: 5
```

#### Soak Test (Long-term Stability)

```yaml
# examples/scenario_soak.yaml
scenarios:
  - name: soak
    duration: 1800    # 30 minutes
    warmup: 10
    cooldown: 5
```

#### Loss Injection Test (Resilience)

```yaml
# examples/scenario_loss.yaml
scenarios:
  - name: loss_injection
    duration: 300
    warmup: 10
    cooldown: 5
generator:
  cameras:
    - ip_address: 192.168.10.11
      gvsp_lost_ratio: 0.01  # 1% packet loss
```

## Operational Procedures

### Pre-Flight Checklist

Before running production tests:

1. **Verify network connectivity**
   ```bash
   python -m gvstress dut inspect --host <dut> --ifaces <ifaces> --json
   ```

2. **Check fakecam status**
   ```bash
   python -m gvstress fakecam status --config <config> --json
   ```

3. **Validate configuration**
   ```bash
   python -m gvstress config validate --config <config>
   ```

4. **Review disk space**
   ```bash
   df -h <artifact-root>
   ```

5. **Check system resources**
   ```bash
   free -h && uptime
   ```

### Running a Production Test

```bash
# 1. Start fakecam workers
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# 2. Run preflight
python -m gvstress dut inspect \
    --host dut.example.com \
    --ifaces eno1,eno2,eno3,eno4 \
    --user admin \
    --json

# 3. Execute soak test
python -m gvstress test soak \
    --config examples/scenario_soak.yaml \
    --output /data/artifacts

# 4. Generate report
python -m gvstress report show --latest --source /data/artifacts/soak/runs

# 5. Stop fakecam
python -m gvstress fakecam down --config examples/fakecam_4p.yaml
```

### Monitoring During Tests

**Real-time metrics:**

```bash
# Watch DUT metrics
watch -n 5 'python -m gvstress dut inspect --host dut --ifaces eno1 --json'

# Monitor artifacts
tail -f artifacts/soak/runs/<run-id>/logs/worker.log
```

**Prometheus queries:**

```promql
# Network throughput
rate(node_network_receive_bytes_total{device="eno1"}[5m])

# CPU usage
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory utilization
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100
```

### Post-Test Procedures

1. **Archive artifacts**
   ```bash
   tar czf soak-$(date +%Y%m%d-%H%M%S).tar.gz artifacts/soak/
   ```

2. **Clean up old runs**
   ```bash
   find artifacts/soak/runs -type d -mtime +30 -exec rm -rf {} +
   ```

3. **Generate trend reports**
   ```bash
   python -m gvstress report trend --source artifacts/soak/runs --days 30
   ```

## Troubleshooting

### Common Issues

#### Fakecam fails to start

**Symptoms:**
```
Error: Failed to start fakecam workers
```

**Causes:**
- Aravis library not installed
- Interface names incorrect in config
- IP addresses not routable
- Insufficient permissions

**Resolution:**
```bash
# Verify Aravis installation
python -c "import gi; gi.require_version('Aravis', '0.8')"

# Check interface names
ip link show

# Verify IP configuration
ip addr show <interface>
```

#### No stream samples collected

**Symptoms:**
- `stream_samples.jsonl` is empty
- Stream metrics all zero

**Causes:**
- Fakecam not running
- Firewall blocking traffic
- Wrong IP addresses in config
- GenICam files missing

**Resolution:**
```bash
# Verify fakecam status
python -m gvstress fakecam status --config <config> --json

# Check firewall
sudo iptables -L -n | grep <port>

# Verify GenICam files
ls -la /usr/share/arv-fakecam/
```

#### Preflight failures

**Symptoms:**
```json
{
  "run_validity": "invalid_prereq",
  "reasons": ["interface eno1 not found"]
}
```

**Resolution:**
1. Review `reasons` in output
2. Fix environment issues
3. Re-run preflight

#### pktgen permission denied

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/proc/net/pktgen/kpktgend_0'
```

**Resolution:**
```bash
# Run with sudo
sudo python -m gvstress baseline pktgen --config <config>

# Or add capability (if using containers)
docker run --cap-add=NET_ADMIN --cap-add=SYS_ADMIN ...
```

### Log Locations

| Component | Log Location |
|-----------|-------------|
| Fakecam workers | `artifacts/<scenario>/logs/fakecam.log` |
| DUT agent | `artifacts/<scenario>/logs/dut_agent.log` |
| Test runner | `artifacts/<scenario>/runs/<run-id>/logs/runner.log` |
| Controller service | `/var/log/gvstress/controller.log` |

### Getting Help

1. **Check documentation:** Review [Testing Guide](testing.md) and [Deployment Guide](deployment.md)
2. **Review logs:** Check component logs for error details
3. **Validate config:** Use `python -m gvstress config validate`
4. **Run preflight:** Use `python -m gvstress dut inspect` to verify environment

## References

- [Testing Guide](testing.md) - Detailed testing procedures
- [Deployment Guide](deployment.md) - Installation and configuration
- [Deployment Architecture ADR](deployment-architecture.md) - Architecture decisions
- [Migration Guide](migration-from-soak-test.md) - Migrating from ad-hoc scripts
