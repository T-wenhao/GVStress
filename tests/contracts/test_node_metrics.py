"""Tests for gvstress node Prometheus metrics."""

import re

import pytest

from gvstress.node.metrics import MetricsRegistry


METRIC_LINE_RE = re.compile(
    r"^(\w+)(\{[^}]*\})?\s+([\d.eE+\-infNaN]+)$"
)
HELP_RE = re.compile(r"^# HELP (\w+) (.+)$")
TYPE_RE = re.compile(r"^# TYPE (\w+) (counter|gauge|histogram|summary|untyped)$")

REQUIRED_METRICS = [
    "gvstress_node_up",
    "gvstress_test_running",
    "gvstress_test_elapsed_seconds",
    "gvstress_test_packets_sent",
    "gvstress_test_pktgen_errors",
    "gvstress_test_expected_packets",
    "gvstress_job_state_info",
    "gvstress_test_verdict_info",
    "gvstress_test_role",
]


class TestMetricsRegistryCreation:
    def test_registry_creates_all_metrics(self):
        reg = MetricsRegistry()
        rendered = reg.render()
        for name in REQUIRED_METRICS:
            assert f"# HELP {name}" in rendered
            assert f"# TYPE {name} gauge" in rendered


class TestNodeUp:
    def test_default_value(self):
        reg = MetricsRegistry()
        reg.set_node_up()
        assert "gvstress_node_up 1" in reg.render()

    def test_set_zero(self):
        reg = MetricsRegistry()
        reg.set_node_up(0)
        assert "gvstress_node_up 0" in reg.render()

    def test_no_labels(self):
        reg = MetricsRegistry()
        reg.set_node_up()
        for line in reg.render().splitlines():
            if line.startswith("gvstress_node_up"):
                assert "{" not in line


class TestTestRunning:
    def test_set_running(self):
        reg = MetricsRegistry()
        reg.set_test_running("smoke")
        assert 'gvstress_test_running{scenario="smoke"} 1' in reg.render()

    def test_set_idle(self):
        reg = MetricsRegistry()
        reg.set_test_running("soak", value=0)
        assert 'gvstress_test_running{scenario="soak"} 0' in reg.render()


class TestTestElapsed:
    def test_set_elapsed(self):
        reg = MetricsRegistry()
        reg.set_test_elapsed("smoke", "abc123", 42.5)
        assert 'gvstress_test_elapsed_seconds{run_id="abc123",scenario="smoke"} 42.5' in reg.render()


class TestPacketsSent:
    def test_set_packets(self):
        reg = MetricsRegistry()
        reg.set_packets_sent("abc123", "eno1", 1000000)
        assert 'gvstress_test_packets_sent{interface="eno1",run_id="abc123"} 1000000' in reg.render()


class TestPktgenErrors:
    def test_set_errors(self):
        reg = MetricsRegistry()
        reg.set_pktgen_errors("abc123", "eno1", 0)
        assert 'gvstress_test_pktgen_errors{interface="eno1",run_id="abc123"} 0' in reg.render()


class TestExpectedPackets:
    def test_set_expected(self):
        reg = MetricsRegistry()
        reg.set_expected_packets("abc123", "eno1", 1000000)
        assert 'gvstress_test_expected_packets{interface="eno1",run_id="abc123"} 1000000' in reg.render()


class TestJobState:
    def test_running_state(self):
        reg = MetricsRegistry()
        reg.set_job_state("running")
        output = reg.render()
        assert 'gvstress_job_state_info{state="running"} 1' in output
        assert 'gvstress_job_state_info{state="idle"} 0' in output

    def test_all_states_present(self):
        reg = MetricsRegistry()
        reg.set_job_state("idle")
        for state in MetricsRegistry.JOB_STATES:
            assert f'state="{state}"' in reg.render()

    def test_only_one_active(self):
        reg = MetricsRegistry()
        reg.set_job_state("completed")
        lines = [
            l for l in reg.render().splitlines()
            if l.startswith("gvstress_job_state_info")
        ]
        active = [l for l in lines if l.endswith(" 1")]
        assert len(active) == 1


class TestVerdict:
    def test_pass_verdict(self):
        reg = MetricsRegistry()
        reg.set_test_verdict("pass", "abc123")
        output = reg.render()
        assert 'gvstress_test_verdict_info{run_id="abc123",verdict="pass"} 1' in output

    def test_all_verdicts_present(self):
        reg = MetricsRegistry()
        reg.set_test_verdict("fail", "xyz")
        for v in MetricsRegistry.VERDICTS:
            assert f'verdict="{v}"' in reg.render()

    def test_only_one_active(self):
        reg = MetricsRegistry()
        reg.set_test_verdict("warn", "abc123")
        lines = [
            l for l in reg.render().splitlines()
            if l.startswith("gvstress_test_verdict_info")
        ]
        active = [l for l in lines if l.endswith(" 1")]
        assert len(active) == 1


class TestRole:
    def test_controller_role(self):
        reg = MetricsRegistry()
        reg.set_test_role("controller")
        output = reg.render()
        assert 'gvstress_test_role{role="controller"} 1' in output

    def test_all_roles_present(self):
        reg = MetricsRegistry()
        reg.set_test_role("dut")
        for r in MetricsRegistry.ROLES:
            assert f'role="{r}"' in reg.render()

    def test_only_one_active(self):
        reg = MetricsRegistry()
        reg.set_test_role("generator")
        lines = [
            l for l in reg.render().splitlines()
            if l.startswith("gvstress_test_role")
        ]
        active = [l for l in lines if l.endswith(" 1")]
        assert len(active) == 1


class TestRenderFormat:
    def test_all_lines_valid(self):
        reg = MetricsRegistry()
        reg.set_node_up()
        reg.set_test_running("smoke")
        reg.set_test_elapsed("smoke", "abc123", 42.5)
        reg.set_packets_sent("abc123", "eno1", 1000000)
        reg.set_pktgen_errors("abc123", "eno1", 0)
        reg.set_expected_packets("abc123", "eno1", 1000000)
        reg.set_job_state("running")
        reg.set_test_verdict("pass", "abc123")
        reg.set_test_role("controller")

        for line in reg.render().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert METRIC_LINE_RE.match(stripped), f"Invalid line: {stripped!r}"

    def test_help_before_type(self):
        reg = MetricsRegistry()
        reg.set_node_up()
        output = reg.render()
        for name in REQUIRED_METRICS:
            help_idx = output.index(f"# HELP {name}")
            type_idx = output.index(f"# TYPE {name}")
            assert help_idx < type_idx

    def test_integer_values_no_decimal(self):
        reg = MetricsRegistry()
        reg.set_node_up()
        assert "gvstress_node_up 1" in reg.render()
        assert "gvstress_node_up 1.0" not in reg.render()

    def test_float_values_preserved(self):
        reg = MetricsRegistry()
        reg.set_test_elapsed("smoke", "abc123", 42.5)
        assert "42.5" in reg.render()


class TestToDict:
    def test_returns_all_metrics(self):
        reg = MetricsRegistry()
        d = reg.to_dict()
        for name in REQUIRED_METRICS:
            assert name in d
            assert "help" in d[name]
            assert "type" in d[name]
            assert "samples" in d[name]
