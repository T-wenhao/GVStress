# Deployment Architecture Decision Record (ADR)

**Status:** Accepted
**Date:** 2026-05-20
**Context:** GVStress deployment modes for data plane (pktgen/fakecam) and control plane

## Decision

GVStress supports three deployment modes, with clear boundaries between data plane and control plane requirements.

## Supported Deployment Modes

### 1. Full Native (Recommended for Production)

All components run natively on bare metal or VMs with systemd service management.

- **Data plane**: GVStress workers and pktgen run as native processes with direct NIC access
- **Control plane**: CLI and orchestration run natively
- **Metrics**: node_exporter + GVStress metrics collected separately

**Use when:** Running real stress tests, benchmarking, or production validation.

### 2. Hybrid (Compose Control + Native Data Nodes)

Control plane services run in Docker Compose; generator/DUT nodes run natively.

- **Control plane**: Docker Compose for dashboard, API, or orchestration services
- **Data plane**: GVStress workers run natively on generator/DUT machines via SSH
- **Communication**: SSH from control container to native nodes, or control runs natively too

**Use when:** You want containerized control services but need bare-metal performance for traffic generation.

### 3. Full Docker Compose (Development / Demo Only)

All components run in Docker Compose for local development or demonstration.

- **WARNING**: Docker bridge networking introduces NAT, MTU changes, and packet overhead
- **NOT suitable** for performance-sensitive pktgen traffic or accurate benchmarks
- **Acceptable** for: UI development, API testing, workflow validation, demos with low traffic

**Use when:** Developing features, testing control-plane logic, or demonstrating the tool.

## Security and Permissions

### `/proc/net/pktgen` Access

The Linux kernel pktgen subsystem requires elevated privileges:

- Writing to `/proc/net/pktgen/` files requires **root** or **CAP_NET_ADMIN**
- GVStress workers that interact with pktgen must run as root or with appropriate capabilities
- **Never** run pktgen workers in unprivileged containers — they will fail silently or crash

**Recommended approach:**
```bash
# Native/systemd service
sudo systemctl start gvstress-worker

# If using Docker (host-network + privileged — see below)
docker run --network host --privileged gvstress/worker
```

### Capability Requirements

| Component | Required Capabilities | Notes |
|-----------|----------------------|-------|
| GVStress fakecam workers | None (user-space Aravis) | Can run unprivileged |
| Pktgen workers | `CAP_NET_ADMIN` or root | Writes to `/proc/net/pktgen/` |
| DUT agent (SSH) | None | Reads `/sys/class/net/` stats |
| node_exporter | None | Standard metrics collection |

## Metrics Architecture

### Separation of Concerns

GVStress metrics and infrastructure metrics are collected separately:

- **node_exporter**: Standard Prometheus node metrics (CPU, memory, disk, network)
  - Runs as a separate systemd service or container
  - Not bundled with GVStress workers
  - Scraped by external Prometheus instance

- **GVStress metrics**: Application-specific metrics (stream health, worker status, test progress)
  - Exposed by GVStress workers themselves
  - Collected via the GVStress reporting pipeline
  - Stored in run artifacts (JSON Lines format)

**Rationale:** Separating these concerns allows:
1. Independent scaling of infrastructure monitoring
2. node_exporter can be shared across multiple workloads
3. GVStress metrics remain tied to specific test runs for attribution

## Docker Networking Warnings

### Docker Bridge is NOT Suitable for Pktgen Traffic

**CRITICAL:** Docker's default bridge network driver:

1. **Adds NAT overhead** — packets are masqueraded, changing source IPs
2. **Modifies MTU** — bridge MTU may differ from physical NIC, causing fragmentation
3. **Introduces latency** — veth pair + bridge forwarding adds microseconds
4. **Breaks pktgen** — `/proc/net/pktgen/` binds to real interfaces, not container veth interfaces

**If you must containerize data-plane components:**

```yaml
# docker-compose.yml — ONLY for development/demo
services:
  gvstress-worker:
    network_mode: host      # Bypass bridge — use host network stack directly
    privileged: true         # Required for /proc/net/pktgen write access
    # OR use specific capabilities instead of full privileged:
    # cap_add:
    #   - NET_ADMIN
    #   - SYS_ADMIN
```

### When `network_mode: host` + `privileged` is Required

| Scenario | network_mode | privileged | Reason |
|----------|-------------|------------|--------|
| Pktgen traffic generation | `host` | `true` or `CAP_NET_ADMIN` | Direct NIC access, `/proc/net/pktgen` writes |
| Fakecam (Aravis) on specific NIC | `host` | `false` | Aravis needs direct interface binding |
| DUT agent (SSH-based) | N/A | `false` | Runs remotely, no container needed |
| Control plane / dashboard | `bridge` (default) | `false` | No NIC access required |

## Summary

| Mode | Data Plane | Control Plane | Use Case |
|------|-----------|---------------|----------|
| Full Native | Native/systemd | Native | Production, benchmarking |
| Hybrid Compose+Native | Native/systemd on remote nodes | Docker Compose | Containerized control, bare-metal data |
| Full Compose (dev) | `host` + `privileged` containers | Docker Compose | Development, demos only |

**Rule of thumb:** If you care about packet-level accuracy, run the data plane natively.
