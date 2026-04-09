# GVStress V1 — Four-Port GigE Vision Stress Validation for I350

## TL;DR
> **Summary**: Build a greenfield Python + PyGObject CLI that runs on a dedicated generator host, orchestrates four `ArvGvFakeCamera` instances, drives a remote DUT over SSH, collects synchronized NIC/stream/system telemetry, and produces run-validity-aware PASS/WARN/FAIL reports.
> **Deliverables**:
> - Installable Python package with `gvstress` CLI and hidden DUT-agent entrypoint
> - Four-camera orchestration, DUT telemetry collectors, scenario engine, verdict engine
> - `run.json` and `summary.md` reports with attribution (`nic`, `stream`, `mixed`, `environment`)
> - Built-in scenarios: `smoke`, `four-stream`, `soak`, `loss-injection`, `pktgen-baseline`
> - Example configs, deployment guide, test guide, hardware-gated acceptance suite
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 2 → 3 → 4 → 5/6/7/8 → 9 → 10 → 11/12 → F1-F4

## Context
### Original Request
Plan V1 only for the highest-priority goal: without physical cameras, simulate four GigE Vision camera streams to validate four-port Intel I350 stability on Linux. Hard requirements: `ArvGvFakeCamera` as primary backend, `pktgen` as baseline tool, CLI-only V1, one fake camera per IP/interface, continuous NIC + stream telemetry, verdict output, and scenarios for single-stream, four-stream, soak, and loss injection.

### Interview Summary
- Workspace is greenfield; no code, tests, build tooling, or CI exists yet.
- Chosen stack: **Python + PyGObject**.
- Chosen topology: **dedicated generator host** runs fake cameras/pktgen; **remote DUT** is controlled over SSH.
- Chosen test strategy: **TDD** with unit + contract + integration tests by default, hardware-marked tests for lab execution.
- V1 remains CLI-only; future TUI/GUI support is reserved only via stable domain/report/event interfaces.

### Metis Review (gaps addressed)
- Locked a strict control boundary: `gvstress` runs on generator host and SSH-invokes the same package on DUT via a hidden `dut-agent` subcommand.
- Added mandatory **preflight gate** and **run_validity** separate from PASS/WARN/FAIL.
- Added deterministic attribution matrix so executors do not infer cause manually from logs.
- Added raw-vs-summary artifact policy to prevent soak reruns when thresholds change.
- Added exact default durations and retention decisions to avoid unresolved edge cases.

## Work Objectives
### Core Objective
Produce a repeatable V1 toolchain that can launch four simulated GigE Vision sources from a dedicated generator host, verify four-port I350 behavior on a Linux DUT, and attribute anomalies to NIC-side issues, stream-consumer issues, mixed evidence, or invalid test environment.

### Deliverables
- Python project scaffold under `src/gvstress/` with installable CLI
- Hidden remote DUT agent path (`gvstress dut-agent ...`) for SSH-driven collection
- Config schema for fake cameras, DUT, stream tuning, scenarios, pktgen baseline, and artifact paths
- Fake camera lifecycle manager with health checks and log archival
- DUT NIC/system/stream collectors with synchronized monotonic timestamps
- Scenario engine for `smoke`, `four-stream`, `soak`, `loss-injection`, `pktgen-baseline`
- Verdict engine with `run_validity`, `verdict`, `primary_attribution`, `secondary_attribution`, and `recommended_actions`
- Report writers for `run.json` and `summary.md`
- Example configs and operator docs for generator host + DUT deployment
- Automated tests plus hardware-gated acceptance suite

### Definition of Done (verifiable conditions with commands)
- `python -m pytest -q -m "not hardware"` exits 0.
- `python -m pytest -q tests/contracts tests/golden` exits 0.
- `python -m gvstress --help` exits 0 and lists `fakecam`, `dut`, `test`, `baseline`, `report`, `dut-agent`.
- `python -m gvstress dut inspect --host dut-lab --ifaces eno1,eno2,eno3,eno4 --json` exits 0 and outputs interface metadata plus environment snapshot paths.
- `python -m gvstress test smoke --config examples/scenario_smoke.yaml --out artifacts/smoke --json` exits 0 in hardware-marked environment and writes `reports/run.json`, `reports/summary.md`, `raw/`, and `evidence/`.
- `python -m gvstress test four-stream --config examples/scenario_4stream.yaml --out artifacts/four-stream --json` exits 0 in hardware-marked environment and `run.json` contains `run_validity="valid"`.
- `python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml --out artifacts/pktgen --json` exits 0 in hardware-marked environment and report classifies output as `baseline_only=true`.
- `python -m gvstress report show latest --json` exits 0 and matches the last generated `run.json` identifiers and verdict fields.

### Must Have
- One package installed on both generator and DUT.
- Generator host launches four local `ArvGvFakeCamera` processes only; DUT never launches fake cameras.
- All remote DUT operations are explicit SSH commands with timeouts, stderr capture, and structured failures.
- `run_validity` values: `valid`, `invalid_environment`, `invalid_prereq`, `invalid_mapping`, `invalid_telemetry`, `interrupted`.
- `verdict` values: `pass`, `warn`, `fail`, `not_applicable`.
- `primary_attribution` values: `nic`, `stream`, `mixed`, `environment`, `unknown`.
- Standard NIC counters are mandatory; driver-specific ethtool counters are best-effort.
- Default scenario durations are fixed in V1: `smoke=60s`, `four-stream=300s`, `soak=1800s`, `loss-injection=300s`, `pktgen-baseline=300s`.
- Loss injection for V1 is implemented **only** through `gvsp-lost-ratio` on selected fake camera instances.
- Runtime sampling cadence is fixed at 1 second in V1 with no downsampling during execution; raw JSONL keeps the full sample stream.
- All reports persist raw samples plus summary fields.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No GUI, deep TUI, Windows support, packet-capture analysis, topology autodetection, plugin system, or custom GVCP/GVSP stack.
- No same-host fake-camera + DUT path as the primary supported validation flow.
- No verdict derived from a single metric without explicit evidence correlation.
- No silent fallback when a required probe, interface mapping, privilege, or dependency is missing.
- No direct comparison claiming pktgen results are protocol-equivalent to GigE Vision.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: **TDD** using `pytest`, contract-fixture tests for shell/SSH parsing, golden tests for reports, integration tests for orchestration, and `hardware`-marked lab tests for end-to-end execution.
- QA policy: Every task below includes agent-executed happy-path and failure/edge-path scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}` during implementation; runtime artifacts use `artifacts/<run-id>/` with `raw/`, `reports/`, `logs/`, `evidence/`.
- Preflight is a hard gate. Any failed prerequisite yields `run_validity != valid` and blocks verdict evaluation.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Shared dependencies are extracted into Wave 1 to maximize later parallelism.

Wave 1: 1 bootstrap/tooling, 2 config-domain schemas, 3 command/SSH runner, 4 preflight/environment, 5 artifact/report models

Wave 2: 6 fake camera manager, 7 DUT NIC/system probes, 8 DUT stream probe

Wave 3: 9 scenario engine/orchestrator, 10 verdict/attribution engine, 11 CLI surface + examples/docs, 12 pktgen baseline

### Dependency Matrix (full, all tasks)
| Task | Depends On | Enables |
|---|---|---|
| 1 | none | 2,3,4,5,6,7,8,9,10,11,12 |
| 2 | 1 | 4,5,6,7,8,9,10,11,12 |
| 3 | 1,2 | 4,7,8,9,11,12 |
| 4 | 1,2,3 | 6,7,8,9,10,11,12 |
| 5 | 1,2 | 9,10,11,12 |
| 6 | 1,2,3,4 | 9,11 |
| 7 | 1,2,3,4 | 9,10,11,12 |
| 8 | 1,2,3,4 | 9,10,11 |
| 9 | 1,2,3,4,5,6,7,8 | 10,11,12 |
| 10 | 2,5,7,8,9 | 11 |
| 11 | 2,3,4,5,6,7,8,9,10 | F1-F4 |
| 12 | 2,3,4,5,7,11 | F1-F4 |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → `quick`, `deep`, `writing`
- Wave 2 → 3 tasks → `deep`, `ultrabrain`
- Wave 3 → 4 tasks → `deep`, `writing`
- Final Verification → 4 review tasks → `oracle`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Bootstrap the Python package, test stack, and CI

  **What to do**: Create a greenfield Python package under `src/gvstress/` with `pyproject.toml`, `python -m gvstress` entrypoint, `pytest`, `ruff`, `mypy`, `pytest-cov`, and a minimal GitHub Actions workflow that runs non-hardware checks only. Use lazy imports so CLI help and unit tests work even when Aravis GI bindings are not installed on a developer machine.
  **Must NOT do**: Do not implement real fake-camera, DUT, verdict, or pktgen logic in this task.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bootstrap is broad but mechanically straightforward.
  - Skills: `[]` - No special skill required.
  - Omitted: `['frontend-ui-ux']` - No UI work in V1.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2,3,4,5,6,7,8,9,10,11,12 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:21-23` - Confirms Python + PyGObject + TDD as locked decisions.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:27-29` - Confirms no existing build/test/CI and that artifact/replay support is required.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:35-36` - Reconfirms V1 scope boundaries.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q` exits 0 with only bootstrap tests present.
  - [ ] `python -m ruff check .` exits 0.
  - [ ] `python -m mypy src` exits 0.
  - [ ] `python -m gvstress --help` exits 0 without importing GI-dependent modules eagerly.
  - [ ] `.github/workflows/ci.yml` runs `pytest`, `ruff`, and `mypy` with `-m "not hardware"` filters where applicable.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Clean bootstrap validation
    Tool: Bash
    Steps: Run `python -m pytest -q && python -m ruff check . && python -m mypy src && python -m gvstress --help` in repo root.
    Expected: All commands exit 0; help text lists top-level command groups.
    Evidence: .sisyphus/evidence/task-1-bootstrap.txt

  Scenario: CLI import without Aravis runtime
    Tool: Bash
    Steps: Run a test that patches `gi` import failure and then executes `python -m gvstress --help`.
    Expected: Help still renders; command exits 0; error is deferred until Aravis-specific commands run.
    Evidence: .sisyphus/evidence/task-1-bootstrap-error.txt
  ```

  **Commit**: YES | Message: `chore(bootstrap): initialize python package and ci` | Files: `pyproject.toml`, `.github/workflows/ci.yml`, `src/gvstress/__main__.py`, `src/gvstress/cli/`, `tests/`

- [x] 2. Define config schema, enums, and run artifact models

  **What to do**: Implement typed config and domain models using Pydantic v2 for fake-camera, DUT, stream, scenario, pktgen, and output settings. Include enums for `run_validity`, `verdict`, `primary_attribution`, `secondary_attribution`, scenario names, and failure reasons. Add YAML loading plus strict validation for duplicate IP/interface mappings, unsupported durations, and invalid `gvsp_lost_ratio` values outside `[0.0, 1.0]`.
  **Must NOT do**: Do not start processes, open SSH sessions, or read live network counters in this task.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: schema design controls every downstream module.
  - Skills: `[]` - Native planning references are sufficient.
  - Omitted: `['refactor']` - No legacy code exists.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3,4,5,6,7,8,9,10,11,12 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:10-13` - Locked required capabilities and acceptance intent.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:16-23` - Locked domain split, topology, and language decisions.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:28-29` - Requires run-validity separation and raw-vs-summary storage.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/unit/test_config_models.py` exits 0.
  - [ ] `python -m pytest -q tests/unit/test_config_validation.py` exits 0.
  - [ ] Loading `tests/fixtures/configs/valid-4port.yaml` produces a model with four unique generator endpoints and four DUT interfaces.
  - [ ] Loading `tests/fixtures/configs/duplicate-ip.yaml` fails with reason `generator.ip_conflict`.
  - [ ] Loading `tests/fixtures/configs/invalid-loss-ratio.yaml` fails with reason `generator.invalid_loss_ratio`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Valid 4-port config load
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_config_models.py::test_valid_4port_config_roundtrip`.
    Expected: Test passes and normalized config preserves four camera-to-port mappings.
    Evidence: .sisyphus/evidence/task-2-config.txt

  Scenario: Duplicate mapping rejection
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_config_validation.py::test_duplicate_camera_ip_rejected`.
    Expected: Test passes by raising validation error containing `generator.ip_conflict`.
    Evidence: .sisyphus/evidence/task-2-config-error.txt
  ```

  **Commit**: YES | Message: `feat(config): add validated scenario and artifact schemas` | Files: `src/gvstress/config/`, `src/gvstress/core/models.py`, `tests/unit/test_config_*.py`, `tests/fixtures/configs/`

- [x] 3. Build the local/SSH command runner and DUT-agent contract

  **What to do**: Implement a command execution layer with two adapters: local subprocess execution on the generator host and remote execution through the system `ssh` client. Standardize timeout handling, stdout/stderr capture, exit codes, monotonic start/stop timestamps, and JSON-line command transcripts. Define the hidden remote contract `python -m gvstress dut-agent <subcommand> ... --json` so the same package can be invoked on DUT over SSH without a long-running daemon.
  **Must NOT do**: Do not bake NIC-specific parsing, fake-camera lifecycle logic, or verdict rules into the command runner.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this boundary controls every generator/DUT interaction.
  - Skills: `[]` - No external skill required.
  - Omitted: `['git-master']` - Not a git task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4,6,7,8,9,11,12 | Blocked By: 1,2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:22` - Dedicated generator host to DUT topology is fixed.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:28` - Environment validity must be explicit and not hidden by transport failures.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/unit/test_runner_local.py tests/unit/test_runner_ssh.py` exits 0.
  - [ ] `python -m pytest -q tests/contracts/test_dut_agent_contract.py` exits 0.
  - [ ] Local runner returns structured records with command, argv, exit code, stdout, stderr, duration, and timeout flag.
  - [ ] SSH runner forms commands using explicit host/user/port options and fails closed on timeout.
  - [ ] DUT-agent contract test proves every remote command can emit JSON to stdout and non-zero exit on invalid subcommand.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Successful remote command contract
    Tool: Bash
    Steps: Run `python -m pytest -q tests/contracts/test_dut_agent_contract.py::test_dut_agent_json_contract`.
    Expected: Contract test passes; stdout is valid JSON; stderr is empty on success.
    Evidence: .sisyphus/evidence/task-3-runner.txt

  Scenario: Timeout and transport failure handling
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_runner_ssh.py::test_ssh_timeout_is_structured_failure`.
    Expected: Test passes and returned error maps to a structured transport failure without stack-trace leakage.
    Evidence: .sisyphus/evidence/task-3-runner-error.txt
  ```

  **Commit**: YES | Message: `feat(runner): add local and ssh execution adapters` | Files: `src/gvstress/core/runner.py`, `src/gvstress/cli/dut_agent.py`, `tests/unit/test_runner_*.py`, `tests/contracts/test_dut_agent_contract.py`

- [x] 4. Implement preflight gating and environment snapshot capture

  **What to do**: Add a preflight workflow that runs before any scenario and validates generator host prerequisites, DUT SSH reachability, binary presence, privilege availability, unique interface/IP mapping, interface link state, MTU, negotiated speed, Aravis presence, `pktgen` availability (for baseline only), and required Linux tools (`ip`, `ethtool`). Capture immutable environment snapshots from both hosts into JSON files before starting any workload.
  **Must NOT do**: Do not start fake cameras, pktgen, or DUT stream acquisition during preflight beyond minimal capability checks.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: preflight determines whether later verdicts are valid.
  - Skills: `[]` - Tooling is straightforward but rules are strict.
  - Omitted: `['playwright']` - No browser work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6,7,8,9,10,11,12 | Blocked By: 1,2,3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:9-10` - I350/igb/MSI-X and required four-camera support must be visible in environment data.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:28` - Environment snapshot is mandatory.
  - External: `https://www.kernel.org/doc/html/latest/networking/statistics.html` - Canonical Linux interface statistics and counter semantics.
  - External: `https://www.kernel.org/doc/html/latest/networking/pktgen.html` - `pktgen` prerequisites and `/proc/net/pktgen` control model.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/unit/test_preflight.py tests/contracts/test_environment_snapshot.py` exits 0.
  - [ ] `python -m gvstress dut inspect --host dut-lab --ifaces eno1,eno2,eno3,eno4 --json --out artifacts/preflight` exits 0 in lab and writes `generator_environment.json`, `dut_environment.json`, and `preflight.json`.
  - [ ] Duplicate IP mapping, missing binaries, SSH failure, down links, or missing privileges produce `run_validity` values other than `valid` and block scenario execution.
  - [ ] `preflight.json` includes `driver`, `driver_version`, `firmware`, `mtu`, `speed`, `msix_detected`, and `irqbalance_detected` fields when obtainable.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Valid preflight with snapshots
    Tool: Bash
    Steps: Run `python -m pytest -q tests/contracts/test_environment_snapshot.py::test_snapshot_merges_generator_and_dut_context`.
    Expected: Test passes and output schema includes both host sections plus mapping information.
    Evidence: .sisyphus/evidence/task-4-preflight.txt

  Scenario: Invalid mapping blocks execution
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_preflight.py::test_duplicate_interface_mapping_marks_invalid_mapping`.
    Expected: Test passes and preflight result is `run_validity=invalid_mapping` with no scenario start side effects.
    Evidence: .sisyphus/evidence/task-4-preflight-error.txt
  ```

  **Commit**: YES | Message: `feat(preflight): gate runs on environment validation` | Files: `src/gvstress/core/preflight.py`, `src/gvstress/dut/environment.py`, `tests/unit/test_preflight.py`, `tests/contracts/test_environment_snapshot.py`

- [x] 5. Define artifact layout and JSON/Markdown report schemas

  **What to do**: Standardize runtime artifact structure as `artifacts/<run-id>/raw/`, `artifacts/<run-id>/logs/`, `artifacts/<run-id>/reports/`, and `artifacts/<run-id>/evidence/`. Store raw periodic samples as JSON Lines (`*.jsonl`) keyed by source (`nic`, `stream`, `system`, `events`). Define versioned `run.json` and `summary.md` render models plus golden tests ensuring summary fields match raw report fields exactly.
  **Must NOT do**: Do not encode verdict thresholds or collector logic in the report renderer.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: schema and human-readable report shape are the focus.
  - Skills: `[]` - Native modeling is enough.
  - Omitted: `['create-github-action-workflow-specification']` - CI spec is not the core output here.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 9,10,11,12 | Blocked By: 1,2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:19` - V1 must emit `run.json` and `summary.md`.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:28-29` - Raw samples and summary output must be stored separately.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/golden/test_run_report.py tests/golden/test_summary_report.py` exits 0.
  - [ ] Golden tests fail if `summary.md` contradicts `run.json` on `run_id`, `run_validity`, `verdict`, or attribution.
  - [ ] `run.json` schema includes `scenario`, `fake_camera_config`, `dut_config`, `stream_config`, `preflight`, `samples`, `verdict`, and `recommended_actions` sections.
  - [ ] `summary.md` includes pass/fail state, affected ports, likely fault domain, and recommended tuning actions.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Golden report consistency
    Tool: Bash
    Steps: Run `python -m pytest -q tests/golden/test_run_report.py::test_run_json_matches_expected_schema tests/golden/test_summary_report.py::test_summary_matches_run_json`.
    Expected: Both golden tests pass.
    Evidence: .sisyphus/evidence/task-5-report.txt

  Scenario: Summary/report mismatch detection
    Tool: Bash
    Steps: Run a negative golden test that injects conflicting verdict fields.
    Expected: Test fails before merge and surfaces exact mismatched field names.
    Evidence: .sisyphus/evidence/task-5-report-error.txt
  ```

  **Commit**: YES | Message: `feat(report): add versioned artifact and report schemas` | Files: `src/gvstress/report/`, `tests/golden/`, `tests/fixtures/reports/`

- [x] 6. Implement generator-side fake camera workers and manager

  **What to do**: Build a generator-host fake-camera subsystem that launches one supervised Python worker process per configured camera. Each worker must import Aravis via PyGObject, instantiate `ArvGvFakeCamera`, apply `interface_name`, `serial_number`, `genicam_filename`, and `gvsp_lost_ratio`, then expose periodic health snapshots based on `is_running` plus process liveness. The manager must own start/stop/status, enforce one-IP-per-camera, archive per-camera logs, and clean up orphaned workers on failure or shutdown.
  **Must NOT do**: Do not embed DUT collection, verdict logic, or packet baseline behavior into the fake-camera manager.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: PyGObject process supervision and health modeling are core V1 risks.
  - Skills: `[]` - No extra skill required.
  - Omitted: `['ulw-loop']` - Not an autonomous indefinite task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,11 | Blocked By: 1,2,3,4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:5` - Primary backend must be `ArvGvFakeCamera`.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:10-11` - Four concurrent fake cameras and continuous telemetry are required.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:17` - One instance per IP/interface is a hard constraint.
  - External: `https://context7.com/aravisproject/aravis/llms.txt` - Confirms fake-camera tooling and Python Aravis bindings exist.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/unit/test_fakecam_manager.py tests/contracts/test_fakecam_worker.py` exits 0.
  - [ ] Manager rejects configs where two fake cameras resolve to the same bound IP.
  - [ ] `python -m gvstress fakecam up --config examples/fakecam_4p.yaml --json --out artifacts/fakecam-up` starts four workers and writes per-camera status JSON plus logs.
  - [ ] `python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json` shows four `running=true` cameras in lab.
  - [ ] `python -m gvstress fakecam down --config examples/fakecam_4p.yaml --json` stops all workers and removes stale pid/state files.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Four camera worker lifecycle
    Tool: Bash
    Steps: Run `python -m pytest -q tests/contracts/test_fakecam_worker.py::test_manager_starts_four_distinct_workers`.
    Expected: Test passes and each worker gets a unique camera identity and state path.
    Evidence: .sisyphus/evidence/task-6-fakecam.txt

  Scenario: Duplicate bind rejection
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_fakecam_manager.py::test_duplicate_ip_binding_is_rejected`.
    Expected: Validation fails before worker start; no partial processes remain.
    Evidence: .sisyphus/evidence/task-6-fakecam-error.txt
  ```

  **Commit**: YES | Message: `feat(fakecam): add supervised aravis fake camera workers` | Files: `src/gvstress/fakecam/`, `src/gvstress/cli/fakecam.py`, `tests/unit/test_fakecam_manager.py`, `tests/contracts/test_fakecam_worker.py`

- [x] 7. Implement DUT NIC and system probes with delta sampling

  **What to do**: Implement remote DUT collectors for standard NIC statistics, driver-defined ethtool counters, link metadata, CPU usage, and IRQ deltas. Use `ip -j -s -s link show dev <iface>` as the canonical source for standard counters; supplement with `/sys/class/net/<iface>/statistics/*`, `ethtool -S`, `ethtool -i`, `ethtool -k`, `ethtool -l`, `/proc/interrupts`, and `/proc/stat`. Store absolute and delta samples per interval, mark unavailable optional counters explicitly, and aggregate results per interface plus across all four ports.
  **Must NOT do**: Do not derive verdicts in the collector; do not silently discard missing counters.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Linux counter semantics and parser stability are critical.
  - Skills: `[]` - No external skill required.
  - Omitted: `['xget']` - No acceleration or registry work involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,10,11,12 | Blocked By: 1,2,3,4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:18` - NIC/driver-specific/IRQ statistics are part of the attribution model.
  - External: `https://www.kernel.org/doc/html/latest/networking/statistics.html` - Canonical definitions for `rtnl_link_stats64`, `ip -s -s`, sysfs, and driver-defined ethtool stats.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/contracts/test_nic_probe_parsers.py tests/contracts/test_system_probe_parsers.py` exits 0.
  - [ ] `python -m pytest -q tests/integration/test_sampling_scheduler.py::test_nic_and_system_samples_produce_deltas` exits 0.
  - [ ] Collector captures at minimum `rx_packets`, `rx_bytes`, `rx_errors`, `rx_dropped`, `rx_over_errors`, `rx_fifo_errors`, `rx_missed_errors`, `tx_packets`, `tx_bytes`, `tx_errors`, `tx_dropped` for each interface.
  - [ ] Missing driver-specific ethtool counters are represented as `available=false` rather than omitted.
  - [ ] CPU and IRQ samples include per-core deltas and can identify a dominant IRQ CPU per interface.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Parse and delta canonical NIC stats
    Tool: Bash
    Steps: Run `python -m pytest -q tests/contracts/test_nic_probe_parsers.py::test_ip_and_ethtool_outputs_map_to_sample_schema`.
    Expected: Parser fixtures pass and output includes standard counters plus best-effort driver counters.
    Evidence: .sisyphus/evidence/task-7-nic-system.txt

  Scenario: Optional counter absence is explicit
    Tool: Bash
    Steps: Run `python -m pytest -q tests/contracts/test_nic_probe_parsers.py::test_missing_driver_stats_are_marked_unavailable`.
    Expected: Test passes and schema records counter availability without crashing or dropping fields.
    Evidence: .sisyphus/evidence/task-7-nic-system-error.txt
  ```

  **Commit**: YES | Message: `feat(dut): add nic and system telemetry probes` | Files: `src/gvstress/dut/nic_probe.py`, `src/gvstress/dut/system_probe.py`, `tests/contracts/test_*probe_parsers.py`, `tests/integration/test_sampling_scheduler.py`

- [x] 8. Implement DUT stream receiver and Aravis statistics probe

  **What to do**: Create a DUT-side Aravis receiver component invoked through `gvstress dut-agent stream-runner ... --json`. It must discover cameras by configured serial/IP, open one stream per fake camera, apply stream properties (`packet-resend`, `socket-buffer`, `socket-buffer-size`, `frame-retention`, `initial-packet-timeout`, `packet-timeout`, `packet-request-ratio`), allocate and recycle buffers continuously, and emit per-stream periodic statistics containing `n_completed_buffers`, `n_failures`, and `n_underruns`. Record configured property snapshots alongside live stats.
  **Must NOT do**: Do not save image payloads or implement reconnection/recovery loops beyond reporting control loss and continuing to sample state.

  **Recommended Agent Profile**:
  - Category: `ultrabrain` - Reason: this is the most protocol-specific and failure-prone integration point.
  - Skills: `[]` - No external skill required.
  - Omitted: `['dev-browser']` - Not a browser task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,10,11 | Blocked By: 1,2,3,4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:18` - Stream stats are part of the attribution model.
  - External: `https://context7.com/aravisproject/aravis/llms.txt` - Python example for `stream.get_statistics()` and stream creation.
  - External: `https://github.com/aravisproject/aravis/blob/main/docs/reference/aravis/ethernet.md` - Stream socket-buffer tuning guidance.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/unit/test_stream_probe_models.py tests/contracts/test_stream_probe_contract.py` exits 0.
  - [ ] `python -m pytest -q -m hardware tests/hardware/test_stream_probe_lab.py::test_four_stream_statistics_capture` exits 0 in lab.
  - [ ] DUT stream runner outputs periodic JSON records with configured properties and cumulative statistics for all active streams.
  - [ ] Stream property snapshot is stored before acquisition starts and repeated in final `run.json`.
  - [ ] A camera with injected `gvsp_lost_ratio > 0` produces detectable non-zero loss symptoms in the stream statistics path during hardware tests.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Four-stream statistics collection
    Tool: Bash
    Steps: Run `python -m pytest -q -m hardware tests/hardware/test_stream_probe_lab.py::test_four_stream_statistics_capture`.
    Expected: Test passes and records per-stream `n_completed_buffers`, `n_failures`, and `n_underruns` snapshots.
    Evidence: .sisyphus/evidence/task-8-stream.txt

  Scenario: Loss-visible stream symptom
    Tool: Bash
    Steps: Run `python -m pytest -q -m hardware tests/hardware/test_stream_probe_lab.py::test_loss_injection_changes_stream_statistics`.
    Expected: Test passes and at least one targeted stream metric changes while untargeted stream fixtures remain stable.
    Evidence: .sisyphus/evidence/task-8-stream-error.txt
  ```

  **Commit**: YES | Message: `feat(stream): add dut-side aravis stream probe` | Files: `src/gvstress/dut/stream_probe.py`, `src/gvstress/cli/dut_agent.py`, `tests/unit/test_stream_probe_models.py`, `tests/contracts/test_stream_probe_contract.py`, `tests/hardware/test_stream_probe_lab.py`

- [x] 9. Build the scenario engine and orchestrator state machine

  **What to do**: Implement a run orchestrator that executes the fixed V1 lifecycle: `preflight -> fakecam_up/pktgen_prepare -> dut_prepare -> warmup -> steady_state -> cooldown -> teardown -> reporting`. Use `sample_interval_ms=1000` by default, `warmup=10s`, `cooldown=5s`, and scenario durations fixed earlier in this plan. Continue collecting evidence until scheduled end even if one stream degrades, unless `run_validity` becomes non-valid due to transport/interruption or all expected fake cameras disappear for more than two consecutive sample intervals. Persist every state transition in the events stream.
  **Must NOT do**: Do not embed verdict thresholds in orchestration logic; do not mutate NIC tuning parameters automatically in V1.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: the orchestrator is the critical path that integrates all subsystems.
  - Skills: `[]` - Native implementation is sufficient.
  - Omitted: `['ralph-loop']` - No autonomous endless loop required.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 10,11 | Blocked By: 1,2,3,4,5,6,7,8

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:10-11` - Required scenarios and continuous metrics collection.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:28-29` - Run validity separation and raw sample persistence.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/integration/test_orchestrator.py tests/integration/test_scenario_engine.py` exits 0.
  - [ ] `tests/integration/test_scenario_engine.py::test_fixed_scenario_durations_and_phase_order` proves `smoke=60s`, `four-stream=300s`, `soak=1800s`, `loss-injection=300s`, and `pktgen-baseline=300s` with 10s warmup and 5s cooldown.
  - [ ] `tests/integration/test_orchestrator.py::test_partial_stream_failure_does_not_abort_before_reportable_evidence` exits 0.
  - [ ] Events stream records all transitions with monotonic timestamps and associated run IDs.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Fixed lifecycle execution
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_scenario_engine.py::test_fixed_scenario_durations_and_phase_order`.
    Expected: Test passes and phase order/durations match the plan exactly.
    Evidence: .sisyphus/evidence/task-9-orchestrator.txt

  Scenario: Evidence preserved after partial degradation
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_orchestrator.py::test_partial_stream_failure_does_not_abort_before_reportable_evidence`.
    Expected: Test passes and orchestrator retains raw samples/events before teardown.
    Evidence: .sisyphus/evidence/task-9-orchestrator-error.txt
  ```

  **Commit**: YES | Message: `feat(orchestrator): add scenario state machine` | Files: `src/gvstress/core/orchestrator.py`, `src/gvstress/core/scenario_engine.py`, `tests/integration/test_orchestrator.py`, `tests/integration/test_scenario_engine.py`

- [x] 10. Implement verdict rules, run-validity handling, and attribution matrix

  **What to do**: Implement a deterministic verdict engine that consumes preflight output, synchronized raw samples, and scenario metadata. Apply these exact V1 rules: (1) if `run_validity != valid`, set `verdict=not_applicable` and `primary_attribution=environment`; (2) map `run_validity` exactly as follows: `invalid_environment` for unsupported OS/kernel/tooling combinations detected before start, `invalid_prereq` for missing binary/privilege/SSH prerequisites, `invalid_mapping` for duplicate or unresolved interface/IP/serial mapping, `invalid_telemetry` for missing required collector output across more than two consecutive sample intervals, and `interrupted` for user cancellation, SSH disconnect after start, or loss of all expected fake cameras for more than two intervals; (3) for `smoke`, `four-stream`, and `soak`, set `pass` only when all expected fake cameras survive, all streams establish within warmup, `n_failures` delta is 0, `n_underruns` delta is 0, and critical NIC counters (`rx_errors`, `rx_dropped`, `rx_over_errors`, `rx_fifo_errors`, `rx_missed_errors`, `tx_errors`, `tx_dropped`) all remain 0; (4) set `warn` for non-injection scenarios only when critical NIC counters stay 0, `n_failures` stays 0, but either total `n_underruns` per stream is between 1 and 3 inclusive, or one CPU owns >=70% of IRQ deltas for >=20% of steady-state samples, or one CPU core exceeds 85% utilization for >=20% of steady-state samples; (5) otherwise set `fail`; (6) for `loss-injection`, set `warn` only if at least one targeted injected stream shows detectable degradation while untargeted streams remain clean, else `fail`. Add recommended-action mapping for `nic`, `stream`, `mixed`, and `environment` attributions.
  **Must NOT do**: Do not introduce fuzzy scoring, ML heuristics, or hidden thresholds outside the explicit rule table above.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is the decision core for PASS/WARN/FAIL and must be deterministic.
  - Skills: `[]` - Native code and tests are sufficient.
  - Omitted: `['review-work']` - Final review happens later in the plan.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 11 | Blocked By: 2,5,7,8,9

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:13` - Report must distinguish NIC-layer vs stream-layer anomalies.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:18` - Attribution uses NIC + stream + IRQ evidence together.
  - External: `https://www.kernel.org/doc/html/latest/networking/statistics.html` - Canonical meaning of critical NIC counters.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/unit/test_verdict_rules.py tests/unit/test_recommended_actions.py` exits 0.
  - [ ] `tests/unit/test_verdict_rules.py::test_valid_clean_four_stream_run_is_pass` exits 0.
  - [ ] `tests/unit/test_verdict_rules.py::test_loss_injection_detected_is_warn` exits 0.
  - [ ] `tests/unit/test_verdict_rules.py::test_invalid_telemetry_run_is_not_applicable` exits 0.
  - [ ] Recommended actions are deterministic and match attribution domain: NIC → MTU/IRQ/MSI-X/offload checks; Stream → socket-buffer/priority/resend/frame-retention tuning; Mixed → both sets; Environment → preflight remediation.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Clean run maps to PASS
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_verdict_rules.py::test_valid_clean_four_stream_run_is_pass`.
    Expected: Test passes and returns `run_validity=valid`, `verdict=pass`, `primary_attribution=unknown` or `nic/stream` only when evidence supports it.
    Evidence: .sisyphus/evidence/task-10-verdict.txt

  Scenario: Invalid evidence never yields PASS
    Tool: Bash
    Steps: Run `python -m pytest -q tests/unit/test_verdict_rules.py::test_invalid_telemetry_run_is_not_applicable`.
    Expected: Test passes and verdict is `not_applicable` with `primary_attribution=environment`.
    Evidence: .sisyphus/evidence/task-10-verdict-error.txt
  ```

  **Commit**: YES | Message: `feat(verdict): add deterministic validity and attribution rules` | Files: `src/gvstress/core/verdict.py`, `src/gvstress/core/recommended_actions.py`, `tests/unit/test_verdict_rules.py`, `tests/unit/test_recommended_actions.py`

- [x] 11. Implement the CLI surface, exit codes, example configs, and operator docs

  **What to do**: Expose the full V1 CLI surface exactly as planned: `fakecam up/status/down`, `dut inspect`, `test smoke`, `test four-stream`, `test soak`, `test loss-injection`, `baseline pktgen`, `report show latest`, and `report export --run-id`. Use `Typer` for CLI parsing, support `--json` on every command, and standardize exit codes: `0=success/pass`, `1=usage or operational error`, `2=warn`, `3=fail`, `4=not_applicable/invalid run`. Add `examples/` configs for fakecam, smoke, four-stream, soak, loss-injection, and pktgen; add `docs/deployment.md` and `docs/testing.md`.
  **Must NOT do**: Do not add GUI/TUI flags, interactive prompts, or hidden automatic retries that change verdict semantics.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: the task combines CLI UX consistency, examples, and operator-facing docs.
  - Skills: `[]` - No special skill needed.
  - Omitted: `['frontend-ui-ux']` - CLI only.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: F1-F4 | Blocked By: 2,3,4,5,6,7,8,9,10

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:7-8` - CLI only; no TUI/GUI in V1.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:19-20` - Report artifacts and CLI-first interaction are fixed.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/integration/test_cli_commands.py tests/golden/test_example_configs.py` exits 0.
  - [ ] `python -m gvstress --help` lists all required commands and `--json` support.
  - [ ] `python -m gvstress test smoke --config examples/scenario_smoke.yaml --json` returns exit code `0`, `2`, `3`, or `4` strictly according to report outcome; never `1` unless invocation/setup fails.
  - [ ] Example config files load successfully under schema tests.
  - [ ] `docs/deployment.md` documents generator-host install, DUT install, SSH prerequisites, required binaries, and lab topology.
  - [ ] `docs/testing.md` documents non-hardware tests, hardware-marked tests, and artifact interpretation.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: CLI command coverage
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_cli_commands.py::test_all_required_subcommands_are_registered`.
    Expected: Test passes and every required V1 subcommand is present.
    Evidence: .sisyphus/evidence/task-11-cli.txt

  Scenario: Exit code contract
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_cli_commands.py::test_scenario_exit_codes_follow_verdict_contract`.
    Expected: Test passes and warn/fail/invalid runs map to exit codes 2/3/4 respectively.
    Evidence: .sisyphus/evidence/task-11-cli-error.txt
  ```

  **Commit**: YES | Message: `feat(cli): add v1 commands examples and operator docs` | Files: `src/gvstress/cli/`, `examples/`, `docs/deployment.md`, `docs/testing.md`, `tests/integration/test_cli_commands.py`, `tests/golden/test_example_configs.py`

- [x] 12. Add pktgen baseline orchestration and comparative baseline summary

  **What to do**: Implement generator-side pktgen support that writes deterministic control scripts/config to artifacts, starts/stops pktgen using `/proc/net/pktgen`, captures per-thread/device results, and combines them with DUT NIC/system telemetry. Treat this as a separate `baseline pktgen` workflow with `baseline_only=true`, plus optional comparison sections embedded in later fake-camera reports when a prior baseline exists for the same interface set. Default baseline duration is 300 seconds and default xmit mode is `start_xmit` with explicit `rate` or `ratep` from config.
  **Must NOT do**: Do not claim pktgen verdicts are equivalent to GigE Vision workload verdicts; do not auto-tune NIC ring/coalescing settings in V1.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: kernel pktgen control, parsing, and safe framing need care.
  - Skills: `[]` - Native implementation is sufficient.
  - Omitted: `['xget']` - No registry/package acceleration involved.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: F1-F4 | Blocked By: 2,3,4,5,7,11

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:6` - `pktgen` is the baseline tool.
  - Pattern: `.sisyphus/drafts/gvstress-v1-4port-i350-validation.md:28` - pktgen is baseline only, not GVSP equivalence.
  - External: `https://www.kernel.org/doc/html/latest/networking/pktgen.html` - Canonical pktgen control model, per-CPU threads, and `/proc/net/pktgen` interface.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python -m pytest -q tests/contracts/test_pktgen_runner.py tests/integration/test_pktgen_baseline.py` exits 0.
  - [ ] `python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml --out artifacts/pktgen --json` exits 0 in lab and writes generated control scripts plus parsed result summary.
  - [ ] Baseline report stores `baseline_only=true`, per-interface throughput, error counts, CPU/IRQ context, and does not reuse scenario PASS/WARN/FAIL semantics.
  - [ ] A later scenario report can reference the most recent compatible baseline by run ID without mutating the original baseline artifact.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Pktgen script and parser roundtrip
    Tool: Bash
    Steps: Run `python -m pytest -q tests/contracts/test_pktgen_runner.py::test_pktgen_script_generation_and_result_parsing`.
    Expected: Test passes and generated control text plus parsed sample output match schema.
    Evidence: .sisyphus/evidence/task-12-pktgen.txt

  Scenario: Baseline remains non-verdicting
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_pktgen_baseline.py::test_baseline_report_is_marked_baseline_only`.
    Expected: Test passes and report sets `baseline_only=true` with no workload PASS/WARN/FAIL classification.
    Evidence: .sisyphus/evidence/task-12-pktgen-error.txt
  ```

  **Commit**: YES | Message: `feat(baseline): add pktgen calibration workflow` | Files: `src/gvstress/baseline/pktgen_runner.py`, `src/gvstress/cli/baseline.py`, `tests/contracts/test_pktgen_runner.py`, `tests/integration/test_pktgen_baseline.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Use one atomic commit per numbered task unless a task is too large and must be split into a test-first commit and a minimal implementation follow-up commit.
- Preserve this order for the critical path: bootstrap → schemas → command runner → preflight → artifacts → collectors/managers → orchestration → verdicts → CLI/docs → pktgen.
- Never mix report-schema changes with verdict semantics unless they are inseparable in the same acceptance test.

## Success Criteria
- Four fake cameras can be launched concurrently with deterministic interface/IP/serial mapping.
- DUT preflight proves environment validity before any scenario starts.
- `smoke`, `four-stream`, `soak`, `loss-injection`, and `pktgen-baseline` all run from CLI with config-driven behavior.
- Reports always include `run_validity`, `verdict`, attribution fields, raw sample references, and recommended actions.
- Non-injection scenarios classify clean runs as `pass`; expected loss-injection runs classify as `warn`; real collection or environment breakdowns never masquerade as `pass`.
