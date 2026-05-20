"""Prometheus metrics for GVStress node.

Generates Prometheus text exposition format metrics for monitoring
and alerting. All metrics follow the contract defined in
docs/metrics-contract.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricSample:
    """A single metric sample with optional labels."""

    labels: dict[str, str] = field(default_factory=dict)
    value: float = 1.0


@dataclass
class MetricDefinition:
    """Definition of a Prometheus metric."""

    name: str
    help_text: str
    metric_type: str = "gauge"
    samples: list[MetricSample] = field(default_factory=list)


class MetricsRegistry:
    """Registry for GVStress Prometheus metrics.

    Collects metric state and renders Prometheus text exposition format.
    """

    JOB_STATES: tuple[str, ...] = ("idle", "preflight", "running", "completed", "failed", "interrupted")
    VERDICTS: tuple[str, ...] = ("pass", "warn", "fail", "not_applicable")
    ROLES: tuple[str, ...] = ("controller", "dut", "generator")

    def __init__(self) -> None:
        self._metrics: dict[str, MetricDefinition] = {}
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize all 9 required metrics."""
        definitions = [
            MetricDefinition(
                name="gvstress_node_up",
                help_text="Health indicator for the GVStress node.",
            ),
            MetricDefinition(
                name="gvstress_test_running",
                help_text="Indicates whether a test scenario is currently active.",
            ),
            MetricDefinition(
                name="gvstress_test_elapsed_seconds",
                help_text="Elapsed time in seconds since the current test started.",
            ),
            MetricDefinition(
                name="gvstress_test_packets_sent",
                help_text="Total number of packets sent by pktgen during the current run.",
            ),
            MetricDefinition(
                name="gvstress_test_pktgen_errors",
                help_text="Number of pktgen errors detected during the current run.",
            ),
            MetricDefinition(
                name="gvstress_test_expected_packets",
                help_text="Expected number of packets to be received by the DUT.",
            ),
            MetricDefinition(
                name="gvstress_job_state_info",
                help_text="Current job state as an info-style metric.",
            ),
            MetricDefinition(
                name="gvstress_test_verdict_info",
                help_text="Test verdict as an info-style metric.",
            ),
            MetricDefinition(
                name="gvstress_test_role",
                help_text="Role of the current GVStress instance in the test topology.",
            ),
        ]
        for defn in definitions:
            self._metrics[defn.name] = defn

    def _get(self, name: str) -> MetricDefinition:
        """Get a metric definition by name."""
        return self._metrics[name]

    def set_node_up(self, value: float = 1.0) -> None:
        """Set gvstress_node_up gauge."""
        m = self._get("gvstress_node_up")
        m.samples = [MetricSample(value=value)]

    def set_test_running(self, scenario: str, value: float = 1.0) -> None:
        """Set gvstress_test_running gauge."""
        m = self._get("gvstress_test_running")
        m.samples = [MetricSample(labels={"scenario": scenario}, value=value)]

    def set_test_elapsed(self, scenario: str, run_id: str, value: float) -> None:
        """Set gvstress_test_elapsed_seconds gauge."""
        m = self._get("gvstress_test_elapsed_seconds")
        m.samples = [
            MetricSample(labels={"scenario": scenario, "run_id": run_id}, value=value)
        ]

    def set_packets_sent(self, run_id: str, interface: str, value: float) -> None:
        """Set gvstress_test_packets_sent gauge."""
        m = self._get("gvstress_test_packets_sent")
        m.samples = [
            MetricSample(labels={"run_id": run_id, "interface": interface}, value=value)
        ]

    def set_pktgen_errors(self, run_id: str, interface: str, value: float) -> None:
        """Set gvstress_test_pktgen_errors gauge."""
        m = self._get("gvstress_test_pktgen_errors")
        m.samples = [
            MetricSample(labels={"run_id": run_id, "interface": interface}, value=value)
        ]

    def set_expected_packets(self, run_id: str, interface: str, value: float) -> None:
        """Set gvstress_test_expected_packets gauge."""
        m = self._get("gvstress_test_expected_packets")
        m.samples = [
            MetricSample(labels={"run_id": run_id, "interface": interface}, value=value)
        ]

    def set_job_state(self, state: str) -> None:
        """Set gvstress_job_state_info gauge.

        Sets the given state to 1 and all other states to 0.
        """
        m = self._get("gvstress_job_state_info")
        m.samples = [
            MetricSample(labels={"state": s}, value=1.0 if s == state else 0.0)
            for s in self.JOB_STATES
        ]

    def set_test_verdict(self, verdict: str, run_id: str) -> None:
        """Set gvstress_test_verdict_info gauge.

        Sets the given verdict to 1 and all others to 0.
        """
        m = self._get("gvstress_test_verdict_info")
        m.samples = [
            MetricSample(
                labels={"verdict": v, "run_id": run_id},
                value=1.0 if v == verdict else 0.0,
            )
            for v in self.VERDICTS
        ]

    def set_test_role(self, role: str) -> None:
        """Set gvstress_test_role gauge.

        Sets the given role to 1 and all others to 0.
        """
        m = self._get("gvstress_test_role")
        m.samples = [
            MetricSample(labels={"role": r}, value=1.0 if r == role else 0.0)
            for r in self.ROLES
        ]

    @staticmethod
    def _format_labels(labels: dict[str, str]) -> str:
        """Format labels as Prometheus label string."""
        if not labels:
            return ""
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return "{" + parts + "}"

    def render(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines: list[str] = []
        for name, metric in self._metrics.items():
            lines.append(f"# HELP {name} {metric.help_text}")
            lines.append(f"# TYPE {name} {metric.metric_type}")
            for sample in metric.samples:
                labels_str = self._format_labels(sample.labels)
                value = sample.value
                # Format integer values without decimal point
                if value == int(value):
                    value_str = str(int(value))
                else:
                    value_str = str(value)
                lines.append(f"{name}{labels_str} {value_str}")
            lines.append("")  # Blank line between metrics

        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        """Return metrics as a dictionary for inspection."""
        result: dict[str, object] = {}
        for name, metric in self._metrics.items():
            result[name] = {
                "help": metric.help_text,
                "type": metric.metric_type,
                "samples": [
                    {"labels": s.labels, "value": s.value} for s in metric.samples
                ],
            }
        return result
