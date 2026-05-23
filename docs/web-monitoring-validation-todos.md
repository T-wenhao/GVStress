# Web Monitoring Validation TODOs

These items remain outside the reliable local validation surface for this
machine. They should be completed on a Linux host with GVStress hardware access
or in an isolated development environment.

## Hardware Smoke

- Run a 5-minute single-node pktgen smoke with real NIC/pktgen access.
- Verify the generated `run.json` and `summary.md` report `pktgen_errors = 0`.
- Verify at least two NIC/system samples are present and IRQ `dominant_cpu` is
  not `unknown` when IRQ deltas exist.

Suggested command:

```bash
python -m pytest tests/hardware -m hardware
```

## Prometheus and Grafana

- Start the monitoring stack on a Linux host.
- Confirm Prometheus scrapes both `gvstress-node` and `node-exporter` targets.
- Confirm Grafana provisions its datasource and dashboards without manual
  clicks.
- Query Prometheus over the smoke-test window for GVStress packets, job state,
  CPU, memory, and network series.

Suggested commands:

```bash
docker compose -f deploy/compose/docker-compose.single.yml config
docker compose -f deploy/compose/docker-compose.single.yml up -d
curl http://localhost:9090/api/v1/targets
curl http://localhost:3000/api/health
```

## Docker Compose Environment

- This repository supports either `docker compose` or `docker-compose`.
- If neither Compose implementation is installed, local tests skip the rendered
  Compose validation while preserving static YAML checks.
- Current local result: `docker compose -f ... config` exits 125 with
  `unknown shorthand flag: 'f'`, and `docker-compose` is not installed.

Suggested fallback:

```bash
docker-compose -f deploy/compose/docker-compose.single.yml config
```

## Ruff and Mypy

- Do not install these tools into the system Python environment.
- If quality gates must be run, create an isolated conda, virtualenv, or
  container environment first.
- Ask for explicit approval before installing dependencies that require network
  access.
- Current local result: `python -m ruff check .` and `python -m mypy src` both
  fail because the modules are not installed in the active Python environment.

Suggested commands inside an isolated environment:

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy src
```

## Local Socket Binding

- Some Web UI tests require binding an ephemeral localhost port.
- In restricted sandboxes where socket binding returns `PermissionError`, those
  tests skip and should be re-run in a normal developer shell or CI runner.

Suggested command:

```bash
python -m pytest tests/test_web_ui.py --no-cov
```
