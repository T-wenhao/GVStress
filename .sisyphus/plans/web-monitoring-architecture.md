# GVStress Web Monitoring Architecture

## TL;DR
> **Summary**: Evolve GVStress from CLI/ad-hoc SSH scripts into a modular Web-controlled test platform with reusable node monitoring, Prometheus/Grafana dashboards, custom GVStress metrics, and single-node/multi-node deployment modes.
> **Deliverables**:
> - `gvstress-node` service for per-host control/metrics
> - `gvstress-controller` API for test orchestration and reports
> - `gvstress-web` Web UI for launch/status/live monitoring/report browsing
> - Prometheus/Grafana/node_exporter deployment pack
> - Native/systemd and Docker Compose deployment scripts
> - Test suite covering unit, integration, service, deployment, and hardware validation
> **Effort**: XL
> **Parallel**: YES - 5 waves
> **Critical Path**: Task 1 → Task 2 → Task 5 → Task 8 → Task 11 → Final Verification

## Context
### Original Request
Analyze current code, determine gap to the target architecture, then formulate a development plan and test content.

### Interview Summary
- Rename the node-side module from `gvstress-agent` to `gvstress-node`.
- Support single-host tests where sender and receiver are on one machine.
- Support multi-host tests where machine A is controller/sender/Web UI and machine B is a lightweight receiver/node.
- Decouple performance collection and Web UI so they can also be used as general NIC monitoring during R&D.
- Use both real-time dashboards and historical retention.
- Initial auth can be omitted or kept to internal-use/simple access.
- Do not hand-roll full monitoring; use mature ecosystem where appropriate.

### Current Code Gap Analysis
- CLI-only entrypoint: `src/gvstress/cli/main.py:14-20` wires Typer commands but no service API or Web UI.
- Minimal dependency set: `pyproject.toml:24-28` has Typer/Pydantic/PyYAML only; no FastAPI, Prometheus client, Web UI, or service dependencies.
- Existing script entrypoint: `pyproject.toml:38-39` exposes only `gvstress` CLI.
- Artifact layout exists and should be reused: `src/gvstress/core/orchestrator.py:43-78` defines raw/report/evidence paths.
- Pktgen baseline runner is synchronous and CLI-oriented: `src/gvstress/cli/baseline.py:111-122` and `src/gvstress/cli/baseline.py:154-199` run collection in-process and stop after `config.pktgen.duration`.
- Pktgen result/report writing exists: `src/gvstress/cli/baseline.py:216-300` writes JSONL samples, `run.json`, and `summary.md`.
- NIC probe is already useful as exporter input: `src/gvstress/dut/nic_probe.py:10-22` defines rx/tx counters, and `src/gvstress/dut/nic_probe.py:75-175` collects per-interface samples and deltas.
- System probe can infer IRQ dominant CPU only when it has at least two samples: `src/gvstress/dut/system_probe.py:83-166` stores previous snapshots; `src/gvstress/dut/system_probe.py:197-230` maps `/proc/interrupts` to interfaces.
- Current ad-hoc `soak_test.py` must not be productized: `soak_test.py:9-12` hard-codes host/user/password/path; `soak_test.py:217-219` currently contains a broken recursive report call with undefined variables.

### Gap Review (Metis-style gaps addressed)
- Avoid confusing `gvstress-node` with existing `dut-agent` command.
- Avoid Docker bridge for datapath; use native/systemd or host-network privileged mode for NIC/pktgen access.
- Treat node_exporter as generic host exporter and GVStress as domain-specific exporter, not a replacement.
- Separate test control plane from raw datapath so Web UI failures do not interrupt active pktgen tests.
- Persist job state and artifacts so long-running 12h/24h runs survive browser/client disconnects.
- Make sampling duration explicit and aligned with pktgen count/duration to avoid one-sample reports and `dominant_cpu=unknown`.
- Do not use system RX packet deltas as exact packet-loss ground truth when promiscuous mode/background traffic is present.
- Remove hard-coded credentials from scripts; use config/env/SSH keys/service permissions.

## Work Objectives
### Core Objective
Build a modular Web-first GVStress platform that can control tests, observe live metrics, retain historical metrics, and generate trustworthy reports across single-host and multi-host topologies.

### Deliverables
- `gvstress-node`: node service exposing local capabilities, test control hooks, local status, and `/metrics`.
- `gvstress-controller`: orchestration API, job persistence, topology management, report indexing.
- `gvstress-web`: browser UI for starting/stopping tests, monitoring live status, viewing Grafana panels, and browsing reports.
- `deploy/`: Docker Compose manifests, native systemd installer, and single-node/two-node bootstrap scripts.
- Prometheus scrape configs, recording rules, and Grafana dashboards.
- Migration path that deprecates ad-hoc `soak_test.py` in favor of supported commands/services.

### Definition of Done (verifiable conditions with commands)
- `python -m pytest tests` passes.
- `python -m pytest tests/contracts tests/integration` passes.
- `gvstress node serve --help`, `gvstress controller serve --help`, and `gvstress web` documented or exposed via deployment scripts.
- `curl http://localhost:<node-port>/metrics` returns GVStress metrics in Prometheus text format.
- `docker compose -f deploy/compose/docker-compose.single.yml config` validates.
- Native install script creates a `gvstress-node` systemd service file without embedding secrets.
- A 5-minute single-node hardware smoke run produces a report, Prometheus samples, Grafana dashboard data, and 0 pktgen errors.

### Must Have
- Single-node and two-node topology models.
- Long-running job state machine: pending/running/stopping/completed/failed.
- Prometheus-compatible custom metrics for test status and pktgen results.
- node_exporter integration for CPU/memory/network counters.
- Report indexing and Web report browsing.
- Explicit deployment mode documentation: native node vs host-network container.

### Must NOT Have
- No Docker bridge datapath for performance-sensitive pktgen traffic.
- No hard-coded IPs, passwords, usernames, or remote paths in product code.
- No reliance on promiscuous RX packet delta as exact loss metric without caveat.
- No Web UI process directly writing `/proc/net/pktgen`; all privileged datapath actions go through `gvstress-node`.
- No monolithic app that prevents reuse of monitoring-only pieces.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed except physical cable setup for hardware tests.
- Test decision: tests-after for architecture/productization, with unit tests added per component before integration tests.
- QA policy: Every task includes agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 domain model, Task 2 node service skeleton, Task 3 metrics contract, Task 4 deployment decision docs
Wave 2: Task 5 controller API, Task 6 node metrics implementation, Task 7 Prometheus/Grafana pack, Task 8 report indexer
Wave 3: Task 9 Web UI, Task 10 single-node deploy scripts, Task 11 two-node orchestration, Task 12 soak-test migration
Wave 4: Task 13 end-to-end validation, Task 14 documentation and operator guide
Wave 5: Final verification wave

### Dependency Matrix (full, all tasks)
- T1 blocks T2, T5, T8, T11.
- T2 blocks T6, T10, T11, T13.
- T3 blocks T6, T7, T9, T13.
- T4 blocks T10, T11, T14.
- T5 blocks T9, T11, T13.
- T6 blocks T7, T13.
- T7 blocks T9, T13.
- T8 blocks T9, T13.
- T9 blocks T13.
- T10 blocks T13.
- T11 blocks T13.
- T12 blocks T14 and reduces risk for T13.
- T13 blocks T14 and final verification.
- T14 blocks final handoff.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 4 tasks → deep, quick, writing
- Wave 2 → 4 tasks → deep, unspecified-high, writing
- Wave 3 → 4 tasks → visual-engineering, deep, unspecified-high
- Wave 4 → 2 tasks → unspecified-high, writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Define topology, node, job, and metrics domain models

  **What to do**: Add typed models for `NodeRole`, `NodeEndpoint`, `TestTopology`, `TestJob`, `JobState`, `MetricTarget`, `DeploymentMode`, and report index records. Place them under a new service/domain module, reusing existing Pydantic style from `src/gvstress/config/models.py`. Include validation for single-node and two-node layouts.
  **Must NOT do**: Do not hard-code `ht`, `192.168.11.139`, `enp8s0`, or `eno1`.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: establishes cross-module contracts.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - no UI work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2,5,8,11 | Blocked By: none

  **References**:
  - Pattern: `src/gvstress/config/models.py:14-16` - existing strict Pydantic model style.
  - API/Type: `src/gvstress/core/models.py` - existing enums and run-domain concepts.
  - Test: `tests/unit/test_config_models.py` - model validation test style.

  **Acceptance Criteria**:
  - [ ] `python -m pytest tests/unit/test_config_models.py tests/unit/test_web_monitoring_models.py` passes.
  - [ ] Invalid topology with same remote node ID twice fails validation.
  - [ ] Valid single-node and two-node topology fixtures load successfully.

  **QA Scenarios**:
  ```
  Scenario: Single-node topology validates
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_web_monitoring_models.py -k single_node`
    Expected: Test passes and model role is both sender and receiver.
    Evidence: .sisyphus/evidence/task-1-models.txt

  Scenario: Invalid topology rejected
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_web_monitoring_models.py -k invalid_topology`
    Expected: ValidationError includes field path and no silent default.
    Evidence: .sisyphus/evidence/task-1-models-error.txt
  ```

  **Commit**: YES | Message: `feat(domain): add node topology models` | Files: `src/gvstress/**`, `tests/unit/**`

- [x] 2. Create `gvstress-node` service skeleton

  **What to do**: Add a node-side service entrypoint with health, capabilities, current status, and safe command hooks. Expose it as a CLI subcommand or script entrypoint. The service must read config from file/env and support native deployment.
  **Must NOT do**: Do not expose raw shell command execution over HTTP.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: service boundary and security-sensitive operations.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - no UI.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6,10,11,13 | Blocked By: 1

  **References**:
  - Pattern: `src/gvstress/cli/main.py:14-20` - CLI subcommand registration.
  - Pattern: `src/gvstress/cli/dut_agent.py:33-57` - simple local agent commands.
  - API/Type: `src/gvstress/core/runner.py` - existing local/SSH command runner abstraction.
  - Test: `tests/contracts/test_dut_agent_contract.py` - agent command contract style.

  **Acceptance Criteria**:
  - [ ] `gvstress node health --json` returns status ok.
  - [ ] `gvstress node capabilities --json` reports interfaces, pktgen availability, and permission state.
  - [ ] Contract tests cover no-shell-injection command API.

  **QA Scenarios**:
  ```
  Scenario: Node health endpoint returns ok
    Tool: Bash
    Steps: Run `python -m gvstress node health --json`
    Expected: JSON contains `status: ok` and exits 0.
    Evidence: .sisyphus/evidence/task-2-node-health.json

  Scenario: Unsafe command rejected
    Tool: Bash
    Steps: Run `python -m pytest tests/contracts/test_node_service_contract.py -k unsafe`
    Expected: Request cannot execute arbitrary shell text.
    Evidence: .sisyphus/evidence/task-2-node-unsafe.txt
  ```

  **Commit**: YES | Message: `feat(node): add gvstress node service skeleton` | Files: `src/gvstress/**`, `tests/contracts/**`

- [x] 3. Define GVStress Prometheus metrics contract

  **What to do**: Define custom `/metrics` names, labels, lifecycle rules, and mapping from current pktgen/NIC/report data. Metrics include test running, elapsed seconds, expected packets, packets sent, pktgen errors, job state, node role, last report verdict, and artifact timestamp.
  **Must NOT do**: Do not duplicate node_exporter CPU/memory/NIC byte counters except when adding domain labels to test-specific status.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: contract-first specification and tests.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - no UI.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6,7,9,13 | Blocked By: none

  **References**:
  - Pattern: `src/gvstress/report/models.py` - report schema fields available for metrics mapping.
  - Pattern: `src/gvstress/cli/baseline.py:302-308` - pktgen return payload data.
  - External: Prometheus exposition format documentation - metrics text format and naming rules.

  **Acceptance Criteria**:
  - [ ] Metrics contract markdown lists every metric name, type, labels, source, and reset behavior.
  - [ ] Parser test validates example `/metrics` output is Prometheus-compatible text.
  - [ ] No metric duplicates node_exporter's raw host counters.

  **QA Scenarios**:
  ```
  Scenario: Metrics fixture parses
    Tool: Bash
    Steps: Run `python -m pytest tests/contracts/test_prometheus_metrics_contract.py`
    Expected: Metrics fixture has valid HELP/TYPE lines and expected labels.
    Evidence: .sisyphus/evidence/task-3-metrics-contract.txt

  Scenario: Duplicate host metrics absent
    Tool: Bash
    Steps: Search generated fixture for `node_cpu_seconds_total` and `node_network_receive_bytes_total`.
    Expected: Neither appears in GVStress custom metrics.
    Evidence: .sisyphus/evidence/task-3-no-duplicates.txt
  ```

  **Commit**: YES | Message: `docs(metrics): define gvstress prometheus contract` | Files: `docs/**`, `tests/contracts/**`

- [x] 4. Write deployment decision record

  **What to do**: Create an architecture decision record explaining native vs container deployment, Docker Compose boundaries, host-network/privileged requirements, and why `gvstress-node` should support native systemd first for datapath reliability.
  **Must NOT do**: Do not claim Docker bridge is acceptable for performance-sensitive pktgen traffic.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: technical decision document.
  - Skills: [] - no special skill needed.
  - Omitted: [`git-master`] - no git operations needed unless committing.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 10,11,14 | Blocked By: none

  **References**:
  - Pattern: `docs/deployment.md` - existing deployment documentation location.
  - Pattern: `README.md:21-27` - current dependency/deployment notes.
  - Evidence: 12h hardware run required host `/proc/net/pktgen` and NIC access.

  **Acceptance Criteria**:
  - [ ] ADR lists supported modes: all-native, mixed compose+native-node, all-compose dev/demo.
  - [ ] ADR includes security/privilege warning for `/proc/net/pktgen`.
  - [ ] ADR references node_exporter and GVStress metrics separation.

  **QA Scenarios**:
  ```
  Scenario: ADR contains deployment matrix
    Tool: Bash
    Steps: Run documentation test that checks headings for single-node, two-node, and dev/demo.
    Expected: All headings present.
    Evidence: .sisyphus/evidence/task-4-adr.txt

  Scenario: ADR rejects Docker bridge datapath
    Tool: Bash
    Steps: Search ADR for explicit Docker bridge warning.
    Expected: Warning present and actionable.
    Evidence: .sisyphus/evidence/task-4-bridge-warning.txt
  ```

  **Commit**: YES | Message: `docs(arch): record deployment architecture` | Files: `docs/**`

- [x] 5. Build controller API and persistent job store

  **What to do**: Add controller service with APIs to create jobs, list jobs, get job status, stop jobs, and resolve artifact/report paths. Start with file-backed storage under artifacts or a lightweight SQLite database; choose file-backed JSON for first version to match current artifact style.
  **Must NOT do**: Do not require a database server in V1.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: orchestration and persistence.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - backend only.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,11,13 | Blocked By: 1

  **References**:
  - Pattern: `src/gvstress/core/orchestrator.py:43-78` - artifact layout.
  - Pattern: `src/gvstress/report/writer.py` - JSON writing style.
  - Pattern: `tests/integration/test_orchestrator.py` - orchestration tests.

  **Acceptance Criteria**:
  - [ ] Create/list/status/stop APIs covered by tests.
  - [ ] Job status survives controller process restart via persisted state.
  - [ ] Controller can index existing `run.json` and `summary.md` artifacts.

  **QA Scenarios**:
  ```
  Scenario: Job persists across restart
    Tool: Bash
    Steps: Run integration test that creates job, reloads store, then reads status.
    Expected: Job ID and state are preserved.
    Evidence: .sisyphus/evidence/task-5-job-store.txt

  Scenario: Stop request updates state
    Tool: Bash
    Steps: Run controller API test for stop transition.
    Expected: running -> stopping -> stopped path is recorded.
    Evidence: .sisyphus/evidence/task-5-stop.txt
  ```

  **Commit**: YES | Message: `feat(controller): add job api and store` | Files: `src/gvstress/**`, `tests/integration/**`

- [x] 6. Implement `gvstress-node` custom `/metrics`

  **What to do**: Add Prometheus text endpoint or CLI-generated text for custom GVStress metrics. Export current job state, pktgen progress, last result, node role, and capability state. Include test-specific labels without high-cardinality raw paths.
  **Must NOT do**: Do not export passwords, raw command lines, or absolute private paths as labels.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: service metrics and security.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - no UI.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7,13 | Blocked By: 2,3

  **References**:
  - Pattern: `src/gvstress/baseline/pktgen_runner.py` - parsed pktgen results.
  - Pattern: `src/gvstress/cli/baseline.py:302-308` - result dict fields.
  - External: Prometheus exposition format documentation.

  **Acceptance Criteria**:
  - [ ] `/metrics` returns 200 and valid Prometheus text.
  - [ ] Metrics include job state and pktgen packets/errors.
  - [ ] Metrics remain available while a long-running test is active.

  **QA Scenarios**:
  ```
  Scenario: Metrics endpoint valid during idle
    Tool: Bash
    Steps: Start node service, curl `/metrics`, run metrics parser test.
    Expected: Valid text with `gvstress_node_up 1`.
    Evidence: .sisyphus/evidence/task-6-metrics-idle.txt

  Scenario: Metrics endpoint valid during fake job
    Tool: Bash
    Steps: Start test fixture job and curl `/metrics`.
    Expected: `gvstress_test_running 1` and packet counters present.
    Evidence: .sisyphus/evidence/task-6-metrics-running.txt
  ```

  **Commit**: YES | Message: `feat(node): expose prometheus metrics` | Files: `src/gvstress/**`, `tests/contracts/**`

- [x] 7. Add Prometheus, node_exporter, and Grafana deployment pack

  **What to do**: Add `deploy/compose` manifests and configuration for Prometheus scraping controller/node/node_exporter targets, plus Grafana dashboards for test status, CPU/memory, network throughput, errors/drops, and IRQ CPU distribution.
  **Must NOT do**: Do not make Grafana required for test execution.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: deployment/config integration.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - dashboard JSON is config, not custom UI.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,13 | Blocked By: 3,6

  **References**:
  - Pattern: `pyproject.toml:24-28` - current dependency minimalism; deployment config should not pollute core deps unnecessarily.
  - External: Prometheus scrape_config docs.
  - External: Grafana provisioning docs.

  **Acceptance Criteria**:
  - [ ] `docker compose -f deploy/compose/docker-compose.single.yml config` succeeds.
  - [ ] Prometheus config includes node_exporter and gvstress-node targets.
  - [ ] Grafana dashboard JSON provisions without manual clicks.

  **QA Scenarios**:
  ```
  Scenario: Compose validates
    Tool: Bash
    Steps: Run `docker compose -f deploy/compose/docker-compose.single.yml config`.
    Expected: Exit 0 and rendered service config includes prometheus/grafana/node-exporter.
    Evidence: .sisyphus/evidence/task-7-compose.txt

  Scenario: Prometheus targets configured
    Tool: Bash
    Steps: Parse `prometheus.yml` and assert expected jobs exist.
    Expected: Jobs for gvstress-node and node_exporter present.
    Evidence: .sisyphus/evidence/task-7-prom-config.txt
  ```

  **Commit**: YES | Message: `feat(deploy): add monitoring compose pack` | Files: `deploy/**`, `tests/**`

- [x] 8. Implement report indexer and report API

  **What to do**: Build a report index that scans existing artifacts, extracts run ID, timestamp, scenario, duration, pktgen stats, report paths, and verdict context. Expose API for listing and reading report summaries.
  **Must NOT do**: Do not rewrite existing report schemas in this task.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: schema compatibility and artifact discovery.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - backend only.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,13 | Blocked By: 1

  **References**:
  - Pattern: `src/gvstress/core/orchestrator.py:43-78` - artifact layout.
  - Pattern: `src/gvstress/cli/report.py` - existing report CLI behavior.
  - Pattern: `tests/integration/test_report_cli_latest.py` - report discovery expectations.

  **Acceptance Criteria**:
  - [ ] Existing `artifacts/**/reports/run.json` can be indexed.
  - [ ] API returns newest runs first.
  - [ ] Corrupt/missing reports are skipped with warning metadata, not crash.

  **QA Scenarios**:
  ```
  Scenario: Existing reports indexed
    Tool: Bash
    Steps: Run report indexer test against fixture artifacts.
    Expected: Known run IDs and summary paths returned.
    Evidence: .sisyphus/evidence/task-8-indexer.txt

  Scenario: Corrupt report skipped
    Tool: Bash
    Steps: Run indexer on fixture with invalid JSON.
    Expected: Valid reports returned and warning emitted.
    Evidence: .sisyphus/evidence/task-8-corrupt.txt
  ```

  **Commit**: YES | Message: `feat(report): add report index api` | Files: `src/gvstress/**`, `tests/integration/**`

- [x] 9. Build Web UI MVP

  **What to do**: Add Web UI for node status, topology selection, test creation, live job status, embedded/link-out Grafana panels, and report browsing. Use controller APIs only.
  **Must NOT do**: Do not run privileged operations from browser or frontend code.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: Web UI/UX.
  - Skills: [`frontend-ui-ux`] - build usable monitoring dashboard flows.
  - Omitted: [`playwright`] - only needed in QA/browser verification stage.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13 | Blocked By: 5,7,8

  **References**:
  - Pattern: controller API from Task 5.
  - Pattern: metrics/dashboard URLs from Task 7.
  - Pattern: report index API from Task 8.

  **Acceptance Criteria**:
  - [ ] UI can create a single-node job from a form.
  - [ ] UI shows running/completed/failed job states.
  - [ ] UI lists reports and opens summary content.
  - [ ] UI provides Grafana dashboard link or embedded panel per job.

  **QA Scenarios**:
  ```
  Scenario: Create single-node job from Web UI
    Tool: Playwright
    Steps: Navigate to UI, select Single Node, choose sender/receiver interfaces, submit.
    Expected: Job appears with state `pending` or `running`.
    Evidence: .sisyphus/evidence/task-9-create-job.png

  Scenario: Browse report from Web UI
    Tool: Playwright
    Steps: Open Reports page and click latest report.
    Expected: Summary renders run ID, duration, pktgen rate, and errors.
    Evidence: .sisyphus/evidence/task-9-report.png
  ```

  **Commit**: YES | Message: `feat(web): add monitoring ui mvp` | Files: `web/**`, `src/gvstress/**`, `tests/**`

- [x] 10. Add native and Compose deployment scripts

  **What to do**: Add `deploy/scripts/install-node-native.sh`, `deploy/systemd/gvstress-node.service`, `deploy/scripts/start-single-node.sh`, and Compose manifests for controller/Web/Prometheus/Grafana. Scripts must be idempotent and require explicit host/interface parameters.
  **Must NOT do**: Do not embed passwords or run destructive commands without confirmation.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: deployment automation with host privileges.
  - Skills: [] - no special skill needed.
  - Omitted: [`xget`] - no download acceleration requirement.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13 | Blocked By: 2,4

  **References**:
  - Pattern: current deployment notes in `docs/deployment.md`.
  - Pattern: `README.md:15-27` - existing install/dependency expectations.
  - External: systemd unit file conventions.

  **Acceptance Criteria**:
  - [ ] `bash -n deploy/scripts/*.sh` passes.
  - [ ] Scripts require `--sender-iface`, `--receiver-iface`, or config file; no defaults to enp8s0/eno1.
  - [ ] systemd service uses config file/env and least necessary privileges documented.

  **QA Scenarios**:
  ```
  Scenario: Script validates arguments
    Tool: Bash
    Steps: Run `deploy/scripts/start-single-node.sh` without args.
    Expected: Exits non-zero with usage text.
    Evidence: .sisyphus/evidence/task-10-script-usage.txt

  Scenario: Compose plus native mode dry run
    Tool: Bash
    Steps: Run script with `--dry-run` for single-node mode.
    Expected: Prints planned services and commands without modifying system.
    Evidence: .sisyphus/evidence/task-10-dry-run.txt
  ```

  **Commit**: YES | Message: `feat(deploy): add native and compose deployment scripts` | Files: `deploy/**`, `docs/**`, `tests/**`

- [x] 11. Implement two-node orchestration

  **What to do**: Add controller support for sender node A and receiver node B. Controller must verify both node health endpoints, configure roles, start sender, monitor receiver, and aggregate report/metrics references.
  **Must NOT do**: Do not require B to run Web UI or Grafana.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: distributed orchestration and failure handling.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - backend/orchestration only.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13 | Blocked By: 1,2,5,10

  **References**:
  - Pattern: `src/gvstress/core/runner.py` - local/SSH command abstraction.
  - Pattern: `src/gvstress/dut/nic_probe.py:75-175` - remote-capable NIC sampling via runner.
  - Pattern: `src/gvstress/cli/dut_agent.py:40-57` - current remote inspect concept.

  **Acceptance Criteria**:
  - [ ] Controller rejects two-node job if either node health check fails.
  - [ ] Receiver metrics target is included in Prometheus scrape config or service discovery output.
  - [ ] Aggregated job status includes sender pktgen stats and receiver rx/error/drop counters.

  **QA Scenarios**:
  ```
  Scenario: Two-node health check passes
    Tool: Bash
    Steps: Run integration test with two fake node services.
    Expected: Controller creates job and stores both node IDs.
    Evidence: .sisyphus/evidence/task-11-two-node-health.txt

  Scenario: Receiver unavailable fails fast
    Tool: Bash
    Steps: Run two-node job with receiver URL unavailable.
    Expected: Job state becomes failed with receiver health reason.
    Evidence: .sisyphus/evidence/task-11-receiver-fail.txt
  ```

  **Commit**: YES | Message: `feat(controller): support two-node orchestration` | Files: `src/gvstress/**`, `tests/integration/**`

- [x] 12. Retire and replace ad-hoc `soak_test.py`

  **What to do**: Move useful lessons from `soak_test.py` into supported services/tests, then remove or quarantine the untracked script. Ensure no hard-coded credentials remain. Add a migration note mapping old commands to Web/controller workflows.
  **Must NOT do**: Do not keep `soak_test.py` as the official 12h/24h entrypoint.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: cleanup once replacement exists.
  - Skills: [] - no special skill needed.
  - Omitted: [`ai-slop-remover`] - may be useful later, but this is removal/migration.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 14 | Blocked By: 5,10,11

  **References**:
  - Anti-pattern: `soak_test.py:9-12` - hard-coded host/user/password/path.
  - Anti-pattern: `soak_test.py:217-219` - current corrupted recursive call.
  - Replacement: controller/node tasks from this plan.

  **Acceptance Criteria**:
  - [ ] No repository file contains `ht123456` or `192.168.11.139` except test fixtures explicitly marked fake.
  - [ ] Official docs point to Web/controller or supported CLI, not `soak_test.py`.
  - [ ] `git status --short` has no accidental untracked operational script.

  **QA Scenarios**:
  ```
  Scenario: Secrets not present
    Tool: Bash
    Steps: Run secret grep for known test password and host IP.
    Expected: No production files contain them.
    Evidence: .sisyphus/evidence/task-12-secret-grep.txt

  Scenario: Migration docs present
    Tool: Bash
    Steps: Run documentation test checking old 12h flow maps to new Web/controller flow.
    Expected: Docs include replacement commands and Web path.
    Evidence: .sisyphus/evidence/task-12-migration-docs.txt
  ```

  **Commit**: YES | Message: `chore(soak): replace ad hoc soak script` | Files: `soak_test.py`, `docs/**`, `tests/**`

- [x] 13. End-to-end validation on single-node and two-node modes

  **What to do**: Run automated integration tests and at least one hardware validation. Single-node hardware run: 5-minute pktgen job with Web/controller, Prometheus samples, report, and Grafana dashboard. Two-node can use fake services first, then documented manual hardware optional.
  **Must NOT do**: Do not mark hardware success based only on Web UI status; verify pktgen result, node metrics, and report artifacts.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: hands-on QA across services.
  - Skills: [`playwright`] - Web UI verification.
  - Omitted: [`frontend-ui-ux`] - UI implementation already complete.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: 14 | Blocked By: 6,7,9,10,11

  **References**:
  - Pattern: `tests/hardware/test_stream_probe_lab.py` - hardware test marker precedent.
  - Pattern: `tests/integration/test_pktgen_baseline.py` - pktgen integration tests.
  - Evidence: Current 12h result demonstrated 3,543,350,400 packets, 0 pktgen errors, but report sampling gaps.

  **Acceptance Criteria**:
  - [ ] Single-node 5-minute hardware run completes with pktgen errors=0.
  - [ ] Prometheus has samples for node_exporter and gvstress-node over the run window.
  - [ ] Web UI report page shows the new run.
  - [ ] `dominant_cpu` is not unknown when there are at least two system samples with IRQ deltas.

  **QA Scenarios**:
  ```
  Scenario: Single-node E2E run
    Tool: Bash + Playwright
    Steps: Deploy single-node stack, create 5-minute job in UI, wait for completion, open report.
    Expected: Report shows 0 pktgen errors, Grafana link available, job completed.
    Evidence: .sisyphus/evidence/task-13-single-node-e2e.md

  Scenario: Metrics retained across run
    Tool: Bash
    Steps: Query Prometheus range API for CPU, memory, network, gvstress packets during job time range.
    Expected: Non-empty samples for all required series.
    Evidence: .sisyphus/evidence/task-13-prometheus-range.json
  ```

  **Commit**: NO | Message: `test(e2e): validate web monitoring stack` | Files: [evidence only]

- [x] 14. Write operator guide and test strategy documentation

  **What to do**: Document architecture, deployment modes, single-node/two-node setup, monitoring interpretation, report semantics, pktgen limitations, and how to interpret RX background traffic. Include test matrix.
  **Must NOT do**: Do not overclaim GigE Vision equivalence for pktgen baseline.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: operator-facing docs.
  - Skills: [] - no special skill needed.
  - Omitted: [`frontend-ui-ux`] - docs only.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: final verification | Blocked By: 4,12,13

  **References**:
  - Pattern: `README.md:111-123` - documentation index style.
  - Pattern: `docs/testing.md` and `docs/deployment.md` - existing docs.
  - Guardrail: `src/gvstress/cli/baseline.py:253` - current pktgen baseline note does not claim GigE Vision equivalence.

  **Acceptance Criteria**:
  - [ ] Docs explain node_exporter vs GVStress custom metrics.
  - [ ] Docs include deployment matrix and commands.
  - [ ] Docs include test matrix: unit, integration, service, compose, hardware, browser.
  - [ ] Docs explain why RX deltas may include background traffic.

  **QA Scenarios**:
  ```
  Scenario: Operator guide links valid
    Tool: Bash
    Steps: Run markdown link check or documentation tests.
    Expected: No broken local links.
    Evidence: .sisyphus/evidence/task-14-doc-links.txt

  Scenario: Test strategy complete
    Tool: Bash
    Steps: Run docs test checking required test categories are present.
    Expected: Unit/integration/service/deploy/hardware/browser categories listed.
    Evidence: .sisyphus/evidence/task-14-test-strategy.txt
  ```

  **Commit**: YES | Message: `docs(web): add operator and test strategy guide` | Files: `docs/**`, `README.md`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright for UI)
- [x] F4. Scope Fidelity Check — deep
## Commit Strategy
- Commit by wave boundary when each wave passes its tests.
- Do not commit operational secrets, local credentials, generated coverage, or ad-hoc hardware artifacts.
- Recommended sequence:
  1. `feat(domain): add node topology models`
  2. `feat(node): add node service and metrics`
  3. `feat(controller): add job orchestration api`
  4. `feat(deploy): add monitoring deployment pack`
  5. `feat(web): add monitoring ui mvp`
  6. `docs(web): add operator guide and test strategy`
## Success Criteria
- User can deploy single-node mode with one documented command/script.
- User can deploy two-node mode with controller on sender and lightweight receiver node.
- Web UI can launch, monitor, stop, and browse tests.
- Prometheus retains node_exporter and GVStress custom metrics for test duration.
- Grafana dashboard shows CPU, memory, NIC throughput/errors/drops, job state, and packet counters.
- Reports remain available as `run.json` and `summary.md` and are browsable through Web UI.
- 5-minute hardware E2E smoke passes with 0 pktgen errors and at least two system/NIC samples.
