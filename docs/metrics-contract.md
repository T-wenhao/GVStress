# GVStress Prometheus Metrics Contract

This document defines the Prometheus metrics exposed by GVStress for monitoring
and alerting purposes. All metrics follow the Prometheus text exposition format.

## Metric Registry

### `gvstress_node_up`

- **Type:** gauge
- **Description:** Health indicator for the GVStress node. Value is `1` when the
  node is operational and reporting metrics, `0` otherwise.
- **Labels:** none
- **Reset behavior:** Set to `0` on shutdown; no reset during normal operation.

### `gvstress_test_running`

- **Type:** gauge
- **Description:** Indicates whether a test scenario is currently active.
  Value is `1` when a test is running, `0` when idle.
- **Labels:**
  - `scenario` — scenario name (e.g. `smoke`, `soak`)
- **Reset behavior:** Set to `0` when the test completes or is interrupted.

### `gvstress_test_elapsed_seconds`

- **Type:** gauge
- **Description:** Elapsed time in seconds since the current test started.
- **Labels:**
  - `scenario` — scenario name
  - `run_id` — unique run identifier
- **Reset behavior:** Reset to `0` at the start of each new test run.

### `gvstress_test_packets_sent`

- **Type:** gauge
- **Description:** Total number of packets sent by pktgen during the current run.
- **Labels:**
  - `run_id` — unique run identifier
  - `interface` — network interface name (e.g. `eno1`)
- **Reset behavior:** Reset to `0` at the start of each new test run.

### `gvstress_test_pktgen_errors`

- **Type:** gauge
- **Description:** Number of pktgen errors detected during the current run.
- **Labels:**
  - `run_id` — unique run identifier
  - `interface` — network interface name
- **Reset behavior:** Reset to `0` at the start of each new test run.

### `gvstress_test_expected_packets`

- **Type:** gauge
- **Description:** Expected number of packets to be received by the DUT, derived
  from the pktgen baseline configuration.
- **Labels:**
  - `run_id` — unique run identifier
  - `interface` — network interface name
- **Reset behavior:** Reset to `0` at the start of each new test run.

### `gvstress_job_state_info`

- **Type:** gauge
- **Description:** Current job state as an info-style metric. Exactly one label
  combination will have value `1` at any time.
- **Labels:**
  - `state` — one of: `idle`, `preflight`, `running`, `completed`, `failed`,
    `interrupted`
- **Reset behavior:** Previous state label set to `0` when transitioning to a
  new state.

### `gvstress_test_verdict_info`

- **Type:** gauge
- **Description:** Test verdict as an info-style metric. Set after test
  completion.
- **Labels:**
  - `verdict` — one of: `pass`, `warn`, `fail`, `not_applicable`
  - `run_id` — unique run identifier
- **Reset behavior:** Reset (all labels set to `0`) at the start of each new
  test run; set once upon completion.

### `gvstress_test_role`

- **Type:** gauge
- **Description:** Role of the current GVStress instance in the test topology.
- **Labels:**
  - `role` — one of: `controller`, `dut`, `generator`
- **Reset behavior:** Does not reset during a process lifetime; set at startup.

## Example Output

See `tests/fixtures/metrics/gvstress_sample.prom` for a complete Prometheus
text-format example.

## Label Conventions

- `run_id`: Unique identifier for a test run, matching the `run_id` field in
  `RunArtifact` (see `src/gvstress/report/models.py`).
- `scenario`: Scenario name, matching `ScenarioType` values.
- `interface`: Network interface name as reported by pktgen.
- `verdict`: Matches the `Verdict` enum: `pass`, `warn`, `fail`, `not_applicable`.
- `state`: Reflects the current lifecycle stage of the test job.

## Reset Semantics

All gauge metrics MUST be reset to `0` at the start of a new test run unless
otherwise noted. Info-style metrics (`*_info`) use the convention that exactly
one label combination carries value `1` at any given time.
