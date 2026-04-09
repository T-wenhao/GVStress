# Deployment Guide

This guide covers installing and configuring GVStress components on generator and DUT (Device Under Test) machines.

## Overview

GVStress consists of:
- **Generator**: Machine running fakecam workers that simulate GigE Vision cameras
- **DUT**: Device under test (e.g., frame grabber, vision system) that receives camera streams
- **Control host**: Machine orchestrating tests (can be same as generator)

## Prerequisites

### Generator Requirements

- Linux OS (Ubuntu 20.04+ recommended)
- Python 3.10+
- Network interfaces with static IPs
- Sufficient CPU for simulated camera count
- Aravis library installed (for fakecam workers)

### DUT Requirements

- SSH access from generator/control host
- Python 3.10+ (for agent deployment)
- Network interfaces connected to generator

## Installation

### Generator Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd GVStress
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Verify installation:
   ```bash
   python -m gvstress --version
   ```

### DUT Agent Installation

The DUT agent runs remotely via SSH. Install on DUT:

1. Copy the gvstress package to DUT:
   ```bash
   scp -r src/gvstress user@dut:/opt/gvstress/
   ```

2. Install dependencies on DUT:
   ```bash
   ssh user@dut "pip install pydantic typer"
   ```

3. Verify agent:
   ```bash
   ssh user@dut "python -m gvstress.cli.dut_agent ping"
   ```

## SSH Configuration

Set up passwordless SSH from generator to DUT:

1. Generate SSH key (if not exists):
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/gvstress -N ""
   ```

2. Copy key to DUT:
   ```bash
   ssh-copy-id -i ~/.ssh/gvstress user@dut
   ```

3. Test connection:
   ```bash
   ssh -i ~/.ssh/gvstress user@dut "hostname"
   ```

## Binary Dependencies

### Aravis (Generator)

Aravis is required for stream probing:

```bash
# Ubuntu/Debian
sudo apt install libaravis-0.8-dev

# Or build from source
git clone https://github.com/AravisProject/aravis
cd aravis
meson build && cd build
ninja && sudo ninja install
```

### Pktgen (Optional)

For baseline benchmarks:

```bash
pip install pktgen
```

## Network Topology

### Typical Setup

```
[Generator]                    [DUT]
  eno1 (192.168.10.1) -------- eno1 (192.168.10.11)
  eno2 (192.168.11.1) -------- eno2 (192.168.11.11)
  eno3 (192.168.12.1) -------- eno3 (192.168.12.11)
  eno4 (192.168.13.1) -------- eno4 (192.168.13.11)
```

### Interface Configuration

On generator, configure static IPs:

```yaml
# /etc/network/interfaces (Debian/Ubuntu)
auto eno1
iface eno1 inet static
    address 192.168.10.1
    netmask 255.255.255.0

auto eno2
iface eno2 inet static
    address 192.168.11.1
    netmask 255.255.255.0
```

Or use NetworkManager:
```bash
nmcli con mod "Wired connection 1" ipv4.addresses "192.168.10.1/24"
nmcli con mod "Wired connection 1" ipv4.method manual
```

## Verification

Run preflight checks before testing:

```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2,eno3,eno4 \
    --json
```

Expected output shows `run_validity=valid` with no error reasons.

## Output Layout

Artifacts are stored in configured output directory:

```
artifacts/
├── fakecam-up/       # Fakecam state
├── preflight/        # Preflight check results
├── runs/             # Test run artifacts
│   └── <run-id>/
│       ├── raw/      # JSON Lines samples
│       ├── reports/  # run.json, summary.md
│       └── logs/     # Worker logs
└── pktgen/           # Baseline benchmarks
```

---

## Chinese Version

This document is available in Chinese: [部署指南 (中文)](deployment-zh.md)
