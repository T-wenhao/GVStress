# GVStress V1 Remediation — Contract Alignment and Wiring Fixes

## TL;DR
> **Summary**: Repair the current GVStress V1 implementation so it actually satisfies the already-approved V1 contract: public CLI/help, remote DUT wiring, structured prereq failures, deterministic verdict execution, aligned examples/docs, and green quality gates.
> **Deliverables**:
> - CLI/help/report paths aligned with the approved V1 plan
> - DUT NIC/system/stream probes wired into scenario execution over the intended control boundary
> - `VerdictEngine` integrated into orchestration with `secondary_attribution` carried through artifacts and summaries
> - Fixed-duration schema enforcement and drift-free examples/docs/goldens
> - Structured invalid-prereq behavior for missing tools like `ethtool`
> - Passing `ruff`, `mypy`, non-hardware tests, and final QA/review wave
> **Effort**: Medium
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → F1-F4

## Context
### Original Request
Based on Atlas’ final review, produce a new development plan to fix the gap between the implemented repository and the previously approved V1 plan.

### Interview Summary
- No new feature scope is requested.
- The approved source of truth remains `.sisyphus/plans/gvstress-v1-4port-i350-validation.md`.
- Docs, examples, CLI help, artifact paths, and report fields are treated as public V1 contract, not “nice to have” derivatives.
- Remediation must be TDD-oriented: each fix starts by locking the broken contract with failing tests or failing characterization checks.

### Metis Review (gaps addressed)
- Do public-contract fixes first; do not bury them inside later cleanup.
- Add `secondary_attribution` model/report plumbing before verdict integration to avoid double churn.
- Use the existing DUT probe construction/preflight taxonomy patterns rather than inventing new abstractions.
- Keep repo-wide lint/type cleanup last so behavioral fixes remain reviewable and atomic.

## Work Objectives
### Core Objective
Restore full compliance with the approved GVStress V1 plan so that the repository’s executable behavior, public CLI/docs/examples, and verification outputs all match the originally planned DUT/generator topology and verdict/reporting contract.

### Deliverables
- Visible `dut-agent` command in top-level CLI help
- Correct `report show --latest` / `report export` artifact-root behavior
- Schema validation for locked V1 scenario durations
- Examples/docs/golden tests aligned with locked plan values
- Scenario execution path that wires DUT NIC/system/stream probes instead of passing `None`
- Structured `invalid_prereq` handling for missing runtime tools without Python traceback leakage
- `RunArtifact` / `SummaryReport` support for `secondary_attribution`
- `RunOrchestrator` integration with `VerdictEngine`
- Root `README.md` matching package metadata and V1 contract
- Green `ruff`, `mypy`, and `pytest -q -m "not hardware"`

### Definition of Done (verifiable conditions with commands)
- `python3 -m gvstress --help` exits 0 and lists `fakecam`, `dut`, `dut-agent`, `test`, `baseline`, `report`.
- `python3 -m pytest -q tests/integration/test_cli_commands.py::test_top_level_help_lists_required_groups` exits 0.
- `python3 -m pytest -q tests/unit/test_config_validation.py::test_locked_v1_durations_are_enforced` exits 0.
- `python3 -m pytest -q tests/integration/test_report_cli_latest.py::test_show_latest_reads_actual_run_root` exits 0.
- `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_scenario_runner_constructs_all_dut_probes` exits 0.
- `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_missing_ethtool_returns_invalid_prereq_without_traceback` exits 0.
- `python3 -m pytest -q tests/unit/test_report_models.py::test_run_artifact_includes_secondary_attribution` exits 0.
- `python3 -m pytest -q tests/integration/test_orchestrator_verdict_integration.py::test_orchestrator_uses_verdict_engine_for_valid_run` exits 0.
- `python3 -m ruff check .` exits 0.
- `python3 -m mypy src` exits 0.
- `python3 -m pytest -q -m "not hardware"` exits 0.

### Must Have
- The remediation must follow the original V1 plan as the sole source of truth.
- Scenario execution must honor the dedicated generator-host → remote DUT topology; no same-host shortcut may become the main path.
- Docs/examples/help must be updated in the same task that changes underlying behavior.
- `secondary_attribution` must exist in report models and be populated by verdict integration, not left as a placeholder.
- Locked V1 durations remain: `smoke=60`, `four_stream=300`, `soak=1800`, `loss_injection=300`, `pktgen_baseline=300`, `warmup=10`, `cooldown=5` unless a scenario is explicitly exempted by the approved plan.
- Missing required dependencies like `ethtool` must become structured `invalid_prereq` outcomes instead of uncaught exceptions.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No new commands, no GUI/TUI work, no plugin system, no topology autodetect.
- No dual artifact-path compatibility layer; fix the real path and update consumers.
- No changing approved durations to match drifted examples/docs.
- No hardcoded verdict values in orchestrator after verdict integration.
- No “best effort” silent bypass when required DUT probes or binaries are unavailable.
- No opportunistic refactor unrelated to restoring the approved V1 contract.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: strict test-first intent inside each task. Each remediation task begins by adding/adjusting failing tests or failing characterization checks, then fixes code/docs/examples/help in the same atomic task.
- QA policy: every task includes both happy-path and failure-path validation.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}` during execution; runtime artifacts remain under the corrected V1 artifact root.
- Quality gate sequencing: behavioral fixes first, repo-wide `ruff`/`mypy` cleanup last.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.

Wave 1: 1 CLI/help contract, 2 artifact/latest contract, 3 fixed-duration contract

Wave 2: 4 DUT probe wiring, 5 structured invalid-prereq behavior, 6 `secondary_attribution` contract

Wave 3: 7 orchestrator/verdict integration, 8 repo quality gate + README + final contract sync

### Dependency Matrix (full, all tasks)
| Task | Depends On | Enables |
|---|---|---|
| 1 | none | 4,8 |
| 2 | none | 8 |
| 3 | none | 8 |
| 4 | 1 | 5,7,8 |
| 5 | 4 | 7,8 |
| 6 | none | 7,8 |
| 7 | 4,5,6 | 8 |
| 8 | 1,2,3,4,5,6,7 | F1-F4 |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 3 tasks → `deep`, `writing`
- Wave 2 → 3 tasks → `deep`, `ultrabrain`
- Wave 3 → 2 tasks → `deep`, `writing`
- Final Verification → 4 review tasks → `oracle`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Restore public CLI/help contract

  **What to do**: Add or update CLI integration tests that lock the top-level public command surface, then expose `dut-agent` in top-level help and align help text with the approved V1 plan. Update any docs/help snapshots touched by this command-surface change in the same task so all public command references are truthful.
  **Must NOT do**: Do not add new command groups or aliases; only restore the approved surface.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this is a public contract and docs/help alignment task.
  - Skills: `[]` - No special skill required.
  - Omitted: `['frontend-ui-ux']` - CLI only.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4,8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:49-57` - Top-level DoD requires `dut-agent` in help output.
  - Drift: `src/gvstress/cli/main.py:13-19` - `dut-agent` is currently registered with `hidden=True`.
  - Pattern: `src/gvstress/cli/main.py:28-38` - Existing Typer callback/version handling should be preserved.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/integration/test_cli_commands.py::test_top_level_help_lists_required_groups` exits 0.
  - [ ] `python3 -m gvstress --help` exits 0 and includes `dut-agent`.
  - [ ] `python3 -m gvstress dut-agent --help` exits 0.
  - [ ] Any docs/help snapshots updated by this task match the actual command surface.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Top-level help exposes full contract
    Tool: interactive_bash
    Steps: Run `python3 -m gvstress --help`; visually confirm `dut-agent` appears alongside `fakecam`, `dut`, `test`, `baseline`, `report`.
    Expected: Command exits 0 and the list matches the approved V1 plan exactly.
    Evidence: .sisyphus/evidence/task-1-cli-help.txt

  Scenario: Hidden command regression blocked
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/integration/test_cli_commands.py::test_top_level_help_lists_required_groups`.
    Expected: Test fails before the fix, passes after the fix.
    Evidence: .sisyphus/evidence/task-1-cli-help-error.txt
  ```

  **Commit**: YES | Message: `test+fix(cli): expose dut-agent in public help` | Files: `src/gvstress/cli/main.py`, `tests/integration/test_cli_commands.py`, touched CLI docs/help snapshots

- [x] 2. Align report latest/export with the planned artifact root

  **What to do**: Add failing report CLI tests that lock the real V1 artifact layout, then align `report show --latest` and `report export` to the same root that scenario/baseline writers actually use. Update docs/help text in the same task. Do not support both old and new layouts.
  **Must NOT do**: Do not create a compatibility shim that searches two roots.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is a contract + path-consistency fix touching report readers and writers.
  - Skills: `[]` - No special skill required.
  - Omitted: `['refactor']` - Limit changes to contract restoration.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:53-57` - `report show latest` must match the last generated run artifact.
  - Drift: `src/gvstress/cli/report.py:33-37` and `src/gvstress/cli/report.py:49-55` - Report CLI currently assumes `artifacts/runs/*`.
  - Pattern: `src/gvstress/cli/test.py:71-74` - Scenario runs write under `output_root / "runs"` from the CLI path today; remediation must reconcile this with the approved root, not duplicate it.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/integration/test_report_cli_latest.py::test_show_latest_reads_actual_run_root` exits 0.
  - [ ] `python3 -m pytest -q tests/integration/test_report_cli_latest.py::test_export_reads_actual_run_root` exits 0.
  - [ ] `python3 -m gvstress report show --latest --json --output <fixture-root>` exits 0 against generated fixture artifacts.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Latest report lookup matches writer layout
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/integration/test_report_cli_latest.py::test_show_latest_reads_actual_run_root`.
    Expected: CLI resolves the newest run from the corrected artifact root and prints the matching `run_id`.
    Evidence: .sisyphus/evidence/task-2-report-latest.txt

  Scenario: Stale path lookup blocked
    Tool: Bash
    Steps: Run a characterization test that seeds only the corrected root and asserts the previous stale root fails pre-fix.
    Expected: Test passes only when stale-root assumptions are removed.
    Evidence: .sisyphus/evidence/task-2-report-latest-error.txt
  ```

  **Commit**: YES | Message: `test+fix(report): align latest lookup with planned artifact root` | Files: `src/gvstress/cli/report.py`, `tests/integration/test_report_cli_latest.py`, touched report docs/help text

- [x] 3. Enforce locked V1 durations and sync drifted examples/docs/goldens

  **What to do**: Add failing config validation tests that reject non-approved V1 scenario durations, warmup, and cooldown values. Implement the exact locked values in schema validation, then update drifted examples, docs, and golden tests to the approved values. Use the approved plan as the sole source of truth.
  **Must NOT do**: Do not make durations configurable in a way that reintroduces drift.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is a contract schema change with multi-file truth alignment.
  - Skills: `[]` - No special skill required.
  - Omitted: `['artistry']` - No unconventional approach needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:67-70` - Locked durations and 1s cadence are explicit.
  - Schema gap: `src/gvstress/config/models.py:144-148` - `ScenarioConfig` currently has no plan-lock validation.
  - Runtime truth: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:67` - `soak=1800`, `warmup=10`, `cooldown=5`.
  - Drift: `examples/scenario_soak.yaml:39-43` - Example currently uses `duration: 3600`, `warmup: 60`, `cooldown: 60`.
  - Drift: `docs/testing.md:9-15` - Docs table currently advertises `soak 3600s`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/unit/test_config_validation.py::test_locked_v1_durations_are_enforced` exits 0.
  - [ ] `python3 -m pytest -q tests/golden/test_example_configs.py::test_scenario_soak_matches_locked_v1_contract` exits 0.
  - [ ] Loading a soak scenario with `3600` fails with a validation error naming `soak` and `1800`.
  - [ ] `examples/scenario_soak.yaml` and `docs/testing.md` both show `soak=1800`, `warmup=10`, `cooldown=5`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Locked duration passes
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/golden/test_example_configs.py::test_scenario_soak_matches_locked_v1_contract`.
    Expected: Example config and docs align with the approved V1 values.
    Evidence: .sisyphus/evidence/task-3-durations.txt

  Scenario: Drifted duration rejected
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/unit/test_config_validation.py::test_locked_v1_durations_are_enforced`.
    Expected: Non-approved duration/warmup/cooldown values are rejected with explicit validation text.
    Evidence: .sisyphus/evidence/task-3-durations-error.txt
  ```

  **Commit**: YES | Message: `test+fix(config): enforce locked v1 durations and sync docs` | Files: `src/gvstress/config/models.py`, `tests/unit/test_config_validation.py`, `tests/golden/test_example_configs.py`, `examples/scenario_*.yaml`, `docs/testing.md`

- [x] 4. Wire DUT probes through scenario execution

  **What to do**: Add failing integration tests proving that the scenario CLI path constructs and passes NIC/system/stream probes into `RunOrchestrator` instead of `None`. Implement the fix by reusing the existing probe-construction approach already present in the baseline path; preserve the dedicated generator-host → DUT topology expected by the V1 plan.
  **Must NOT do**: Do not invent a second probe-construction abstraction if the baseline path already provides the needed pattern.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is the highest-risk behavioral wiring fix in the user path.
  - Skills: `[]` - No special skill required.
  - Omitted: `['ulw-loop']` - Finite integration fix.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5,7,8 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:41-45` - DUT NIC/system/stream collectors and verdict/report pipeline are required deliverables.
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:60-63` - Remote DUT operations must be explicit and structured.
  - Drift: `src/gvstress/cli/test.py:71-84` - Orchestrator is currently constructed with all DUT probes set to `None`.
  - Pattern: `src/gvstress/cli/baseline.py:96-99` - Baseline path already resolves NIC/system probes before execution.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_scenario_runner_constructs_all_dut_probes` exits 0.
  - [ ] `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_scenario_runner_passes_probes_into_orchestrator` exits 0.
  - [ ] No scenario CLI path passes `None` for required DUT probes when the plan requires collection.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Scenario CLI wires probes
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_scenario_runner_constructs_all_dut_probes`.
    Expected: Test confirms NIC/system/stream probes are instantiated from config and passed into the orchestrator.
    Evidence: .sisyphus/evidence/task-4-probe-wiring.txt

  Scenario: None-probe regression blocked
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_scenario_runner_passes_probes_into_orchestrator`.
    Expected: Test would fail if any required probe argument is `None`.
    Evidence: .sisyphus/evidence/task-4-probe-wiring-error.txt
  ```

  **Commit**: YES | Message: `test+fix(orchestration): wire dut probes through scenario cli` | Files: `src/gvstress/cli/test.py`, `tests/integration/test_cli_execution_contracts.py`, related probe construction helpers

- [x] 5. Make missing runtime tools produce structured invalid-prereq behavior

  **What to do**: Add failing CLI/integration tests that simulate missing required host tools such as `ethtool`, then ensure the scenario and DUT-inspect paths convert those failures into structured `invalid_prereq` results or controlled exit behavior without Python traceback leakage. Reuse the existing preflight invalid-prereq taxonomy; do not invent a new one.
  **Must NOT do**: Do not swallow unrelated runtime exceptions into `invalid_prereq`.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this crosses preflight, CLI error handling, and contract-level exit behavior.
  - Skills: `[]` - No special skill required.
  - Omitted: `['dev-browser']` - CLI only.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 7,8 | Blocked By: 4

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:75-77` - No silent fallback when required dependency is missing.
  - Pattern: `src/gvstress/core/preflight.py:199-225` - Existing structured prereq classification should be reused.
  - Observed failure path: `src/gvstress/cli/test.py:55-61` - Scenario path currently calls preflight but Atlas QA observed uncaught `FileNotFoundError` for `ethtool`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_missing_ethtool_returns_invalid_prereq_without_traceback` exits 0.
  - [ ] `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_dut_inspect_missing_ethtool_is_controlled_error` exits 0.
  - [ ] Failure output names the missing binary and contains no Python traceback.
  - [ ] Invalid-prereq results remain machine-readable under `--json`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Missing ethtool is structured
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/integration/test_cli_execution_contracts.py::test_missing_ethtool_returns_invalid_prereq_without_traceback`.
    Expected: CLI reports controlled invalid-prereq behavior, not a traceback.
    Evidence: .sisyphus/evidence/task-5-invalid-prereq.txt

  Scenario: Unexpected exception not misclassified
    Tool: Bash
    Steps: Run a negative integration test that injects a non-prereq runtime failure.
    Expected: Test proves only real missing-prereq cases map to `invalid_prereq`.
    Evidence: .sisyphus/evidence/task-5-invalid-prereq-error.txt
  ```

  **Commit**: YES | Message: `test+fix(preflight): return structured invalid-prereq errors` | Files: `src/gvstress/core/preflight.py`, `src/gvstress/cli/dut.py`, `src/gvstress/cli/test.py`, `tests/integration/test_cli_execution_contracts.py`

- [x] 6. Add secondary attribution to artifact and summary contracts

  **What to do**: Add failing unit/golden tests that require `secondary_attribution` to exist in artifact/report models and serialized outputs. Then extend the relevant report models, writers, renderers, and tests so the field is present everywhere required by the approved plan before verdict integration begins using it.
  **Must NOT do**: Do not add a placeholder field that is never populated by the runtime path.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is a cross-model contract change needed before verdict wiring.
  - Skills: `[]` - No special skill required.
  - Omitted: `['writing']` - Primarily model/serialization work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7,8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:44` - Deliverables explicitly include `secondary_attribution`.
  - Gap: `src/gvstress/report/models.py:65-90` - `RunArtifact` currently has `primary_attribution` but no `secondary_attribution`.
  - Gap: `src/gvstress/report/models.py:124-132` - `VerdictSummary` also lacks `secondary_attribution`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/unit/test_report_models.py::test_run_artifact_includes_secondary_attribution` exits 0.
  - [ ] `python3 -m pytest -q tests/golden/test_summary_report.py::test_summary_includes_secondary_attribution` exits 0.
  - [ ] Serialized `run.json` and rendered `summary.md` both surface `secondary_attribution` once the field is set.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Artifact model includes secondary attribution
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/unit/test_report_models.py::test_run_artifact_includes_secondary_attribution`.
    Expected: Model construction and serialization both require and preserve the field.
    Evidence: .sisyphus/evidence/task-6-secondary-attribution.txt

  Scenario: Summary rendering does not drop field
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/golden/test_summary_report.py::test_summary_includes_secondary_attribution`.
    Expected: Golden output contains the secondary attribution section/value.
    Evidence: .sisyphus/evidence/task-6-secondary-attribution-error.txt
  ```

  **Commit**: YES | Message: `test+fix(report): add secondary attribution contract` | Files: `src/gvstress/report/models.py`, `src/gvstress/report/renderer.py`, `src/gvstress/report/writer.py`, `tests/unit/test_report_models.py`, `tests/golden/test_summary_report.py`

- [x] 7. Replace hardcoded verdict assignment with verdict engine integration

  **What to do**: Add failing orchestration tests that prove valid and invalid runs must be evaluated through `VerdictEngine`, then integrate the engine into `RunOrchestrator` so artifact and summary outputs are driven by engine decisions instead of hardcoded `PASS` / `NOT_APPLICABLE`. Populate both primary and secondary attribution as part of the same task.
  **Must NOT do**: Do not duplicate verdict logic in orchestrator.

  **Recommended Agent Profile**:
  - Category: `ultrabrain` - Reason: this is the most consequential integration point for runtime truthfulness.
  - Skills: `[]` - No special skill required.
  - Omitted: `['review-work']` - Final review happens later.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 8 | Blocked By: 4,5,6

  **References** (executor has NO interview context - be exhaustive):
  - Contract: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:44` and `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:63-65` - Verdict fields and values are locked.
  - Gap: `src/gvstress/core/orchestrator.py:444-472` - Orchestrator currently hardcodes verdict/attribution at report-write time.
  - Engine: `src/gvstress/core/verdict.py:87-180` - `VerdictEngine.evaluate()` already defines the intended deterministic decision path.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python3 -m pytest -q tests/integration/test_orchestrator_verdict_integration.py::test_orchestrator_uses_verdict_engine_for_valid_run` exits 0.
  - [ ] `python3 -m pytest -q tests/integration/test_orchestrator_verdict_integration.py::test_invalid_run_maps_to_not_applicable_via_engine_contract` exits 0.
  - [ ] `run.json` and `summary.md` contain engine-derived `verdict`, `primary_attribution`, `secondary_attribution`, and `recommended_actions`.
  - [ ] No code path in orchestrator directly assigns valid runs to `PASS` without engine evaluation.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Valid run goes through engine
    Tool: Bash
    Steps: Run `python3 -m pytest -q tests/integration/test_orchestrator_verdict_integration.py::test_orchestrator_uses_verdict_engine_for_valid_run`.
    Expected: The test proves the orchestrator calls the verdict engine and persists its decision.
    Evidence: .sisyphus/evidence/task-7-verdict-wiring.txt

  Scenario: Hardcoded PASS regression blocked
    Tool: Bash
    Steps: Run a characterization test that would fail if orchestrator directly sets `Verdict.PASS` for valid runs.
    Expected: Test passes only when direct hardcoding is removed.
    Evidence: .sisyphus/evidence/task-7-verdict-wiring-error.txt
  ```

  **Commit**: YES | Message: `test+fix(orchestrator): route results through verdict engine` | Files: `src/gvstress/core/orchestrator.py`, `src/gvstress/core/verdict.py`, `tests/integration/test_orchestrator_verdict_integration.py`, `tests/golden/test_run_report.py`, `tests/golden/test_summary_report.py`

- [x] 8. Restore repo quality gates and final contract truthfulness

  **What to do**: After all behavioral fixes are in place, add/restore the missing root `README.md`, align it with package metadata and the approved V1 contract, then make the repository green under `ruff`, `mypy`, and non-hardware pytest. Fix only issues required to make the remediated codebase pass those gates; avoid opportunistic cleanup. Re-run CLI/manual QA scenarios that previously exposed `ethtool` and stale-path failures.
  **Must NOT do**: Do not turn this into a broad formatting/refactor pass.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this task is half docs/contract truthfulness and half gate cleanup.
  - Skills: `[]` - No special skill required.
  - Omitted: `['skill-creator']` - Not relevant.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: F1-F4 | Blocked By: 1,2,3,4,5,6,7

  **References** (executor has NO interview context - be exhaustive):
  - Packaging contract: `pyproject.toml:5-10` - Package metadata requires `README.md`.
  - Quality gate: `.sisyphus/plans/gvstress-v1-4port-i350-validation.md:49-57` - Original DoD still requires `pytest`, CLI, report commands, and valid artifacts.
  - Atlas finding: final review reported existing `ruff` and `mypy` failures that must be closed before approval.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `test -f README.md` succeeds.
  - [ ] `python3 -m ruff check .` exits 0.
  - [ ] `python3 -m mypy src` exits 0.
  - [ ] `python3 -m pytest -q -m "not hardware"` exits 0.
  - [ ] `python3 -m gvstress dut inspect --host localhost --ifaces eno1 --json` fails in a controlled, non-traceback manner when prerequisites are intentionally absent.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Repository quality gates green
    Tool: Bash
    Steps: Run `python3 -m ruff check . && python3 -m mypy src && python3 -m pytest -q -m "not hardware"`.
    Expected: All commands exit 0.
    Evidence: .sisyphus/evidence/task-8-quality-gates.txt

  Scenario: Prior manual QA failures stay fixed
    Tool: interactive_bash
    Steps: Re-run `python3 -m gvstress --help`, `python3 -m gvstress dut inspect --host localhost --ifaces eno1 --json`, and `python3 -m gvstress report show --latest --output <fixture-root>`.
    Expected: Help is truthful; missing-prereq errors are controlled; report latest resolves correctly.
    Evidence: .sisyphus/evidence/task-8-quality-gates-error.txt
  ```

  **Commit**: YES | Message: `docs+chore(repo): restore readme and make gates green` | Files: `README.md`, touched source/test/docs files required for green gates

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Remediation Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Use one atomic remediation commit per numbered task.
- Every commit must include tests/docs/examples/help updates needed to make that contract slice truthful.
- Do not interleave repo-wide lint/type cleanup before behavioral remediation commits land.

## Success Criteria
- The repository behavior matches the approved V1 plan, not the previously drifted implementation.
- CLI/help/docs/examples/report paths all tell the same story and are executable.
- Scenario runs wire DUT probes and route outcomes through `VerdictEngine`.
- `secondary_attribution` exists end-to-end in artifacts and summaries.
- Missing runtime tools become structured prereq failures, not uncaught tracebacks.
- `ruff`, `mypy`, and non-hardware pytest are green.
