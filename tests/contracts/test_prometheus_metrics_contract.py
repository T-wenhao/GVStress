# pyright: reportMissingImports=false, reportMissingTypeStubs=false

"""Contract tests for GVStress Prometheus metrics.

Validates that the metrics fixture file contains all 9 required metrics
with correct HELP/TYPE lines, valid label formats, and proper Prometheus
text exposition format.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "metrics" / "gvstress_sample.prom"

REQUIRED_METRICS = {
    "gvstress_node_up": {"type": "gauge", "labels": set()},
    "gvstress_test_running": {"type": "gauge", "labels": {"scenario"}},
    "gvstress_test_elapsed_seconds": {"type": "gauge", "labels": {"scenario", "run_id"}},
    "gvstress_test_packets_sent": {"type": "gauge", "labels": {"run_id", "interface"}},
    "gvstress_test_pktgen_errors": {"type": "gauge", "labels": {"run_id", "interface"}},
    "gvstress_test_expected_packets": {"type": "gauge", "labels": {"run_id", "interface"}},
    "gvstress_job_state_info": {"type": "gauge", "labels": {"state"}},
    "gvstress_test_verdict_info": {"type": "gauge", "labels": {"verdict", "run_id"}},
    "gvstress_test_role": {"type": "gauge", "labels": {"role"}},
}

HELP_RE = re.compile(r"^# HELP (\w+) (.+)$")
TYPE_RE = re.compile(r"^# TYPE (\w+) (counter|gauge|histogram|summary|untyped)$")
METRIC_RE = re.compile(r"^(\w+)(\{[^}]*\})?\s+([\d.eE+\-infNaN]+)$")


def parse_prometheus_file(path: Path) -> dict:
    """Parse a Prometheus text-format file into structured data."""
    metrics: dict[str, dict] = {}
    current_help: dict[str, str] = {}
    current_type: dict[str, str] = {}

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("# EOF"):
                continue

            help_match = HELP_RE.match(line)
            if help_match:
                name, description = help_match.groups()
                current_help[name] = description
                continue

            type_match = TYPE_RE.match(line)
            if type_match:
                name, metric_type = type_match.groups()
                current_type[name] = metric_type
                continue

            metric_match = METRIC_RE.match(line)
            if metric_match:
                name, labels_str, value = metric_match.groups()
                labels: dict[str, str] = {}
                if labels_str:
                    for pair in labels_str.strip("{}").split(","):
                        key, val = pair.split("=", 1)
                        labels[key] = val.strip('"')

                if name not in metrics:
                    metrics[name] = {
                        "samples": [],
                        "all_label_keys": set(),
                    }
                metrics[name]["samples"].append({"labels": labels, "value": value})
                metrics[name]["all_label_keys"].update(labels.keys())

    return {
        "metrics": metrics,
        "help": current_help,
        "types": current_type,
    }


@pytest.fixture(scope="module")
def parsed_fixture():
    """Parse the Prometheus fixture file once for all tests."""
    assert FIXTURE_PATH.exists(), f"Fixture file not found: {FIXTURE_PATH}"
    return parse_prometheus_file(FIXTURE_PATH)


class TestAllMetricsPresent:
    """Verify all 9 required metrics exist in the fixture."""

    @pytest.mark.parametrize("metric_name", sorted(REQUIRED_METRICS.keys()))
    def test_metric_exists(self, parsed_fixture, metric_name):
        assert metric_name in parsed_fixture["metrics"], (
            f"Missing required metric: {metric_name}"
        )


class TestMetricTypes:
    """Verify each metric has the correct TYPE declaration."""

    @pytest.mark.parametrize("metric_name", sorted(REQUIRED_METRICS.keys()))
    def test_metric_type(self, parsed_fixture, metric_name):
        expected_type = REQUIRED_METRICS[metric_name]["type"]
        actual_type = parsed_fixture["types"].get(metric_name)
        assert actual_type == expected_type, (
            f"{metric_name}: expected type '{expected_type}', got '{actual_type}'"
        )


class TestMetricHelp:
    """Verify each metric has a HELP line."""

    @pytest.mark.parametrize("metric_name", sorted(REQUIRED_METRICS.keys()))
    def test_metric_has_help(self, parsed_fixture, metric_name):
        assert metric_name in parsed_fixture["help"], (
            f"{metric_name}: missing HELP line"
        )
        assert len(parsed_fixture["help"][metric_name]) > 0, (
            f"{metric_name}: HELP line is empty"
        )


class TestMetricLabels:
    """Verify metrics have the expected label keys."""

    @pytest.mark.parametrize("metric_name", sorted(REQUIRED_METRICS.keys()))
    def test_metric_labels(self, parsed_fixture, metric_name):
        expected_labels = REQUIRED_METRICS[metric_name]["labels"]
        if not expected_labels:
            return  # No labels expected

        metric_data = parsed_fixture["metrics"].get(metric_name)
        assert metric_data is not None, f"{metric_name}: metric not found"

        # Check that at least one sample has all expected label keys
        found = False
        for sample in metric_data["samples"]:
            if expected_labels.issubset(sample["labels"].keys()):
                found = True
                break
        assert found, (
            f"{metric_name}: expected labels {expected_labels}, "
            f"but no sample contains all of them"
        )


class TestMetricValues:
    """Verify metric values are valid numbers."""

    @pytest.mark.parametrize("metric_name", sorted(REQUIRED_METRICS.keys()))
    def test_metric_values_are_numeric(self, parsed_fixture, metric_name):
        metric_data = parsed_fixture["metrics"].get(metric_name)
        assert metric_data is not None, f"{metric_name}: metric not found"
        assert len(metric_data["samples"]) > 0, (
            f"{metric_name}: no data samples found"
        )

        for sample in metric_data["samples"]:
            value = sample["value"]
            try:
                float(value)
            except ValueError:
                pytest.fail(
                    f"{metric_name}: invalid numeric value '{value}'"
                )


class TestFixtureFormat:
    """Verify the fixture file is valid Prometheus text format."""

    def test_file_exists(self):
        assert FIXTURE_PATH.exists(), f"Fixture file not found: {FIXTURE_PATH}"

    def test_file_not_empty(self):
        content = FIXTURE_PATH.read_text()
        assert len(content) > 0, "Fixture file is empty"

    def test_no_blank_metric_lines(self):
        """Ensure no metric lines are malformed (blank name or value)."""
        with open(FIXTURE_PATH) as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                match = METRIC_RE.match(stripped)
                assert match is not None, (
                    f"Line {line_num}: invalid metric format: {stripped!r}"
                )
