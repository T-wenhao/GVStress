from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import cast

from gvstress.report.models import SCHEMA_VERSION
from gvstress.report.renderer import MarkdownRenderer
from tests.fixtures.reports.helpers import FixtureBuilder


def _render_markdown(report: object) -> str:
    render = cast(Callable[[object], str], MarkdownRenderer().render)
    return render(report)


def test_summary_includes_secondary_attribution(tmp_path: Path) -> None:
    builder = FixtureBuilder(tmp_path)
    report = builder.build_summary_report(secondary_attribution="stream_configuration")
    markdown = _render_markdown(report)

    assert "**Secondary Attribution:** stream_configuration" in markdown


class TestSummaryReportStructure:
    def test_required_fields(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()

        assert report.run_id == "test-run-001"
        assert report.scenario_name.value == "four_stream"
        assert report.scenario_duration == 300
        assert report.preflight.run_validity.value == "valid"

    def test_schema_version_default(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        assert report.schema_version == SCHEMA_VERSION


class TestMarkdownRendering:
    def test_render_header(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(run_id="test-123")
        markdown = _render_markdown(report)

        assert "# GVStress Run Report: test-123" in markdown
        assert f"**Schema Version:** {SCHEMA_VERSION}" in markdown

    def test_render_scenario_section(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        assert "## Scenario" in markdown
        assert "**Type:** four_stream" in markdown
        assert "**Duration:** 300s" in markdown

    def test_render_preflight_section(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        assert "## Preflight" in markdown
        assert "**Validity:** valid" in markdown
        assert "**Checks Passed:** 5" in markdown

    def test_render_samples_section(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        assert "## Collected Samples" in markdown
        assert "**NIC Samples:** 150" in markdown
        assert "**Stream Samples:** 150" in markdown

    def test_render_verdict_section_pass(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(verdict="pass")
        markdown = _render_markdown(report)

        assert "## Verdict" in markdown
        assert "**Result:** ✅ PASS" in markdown

    def test_render_verdict_section_fail(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(verdict="fail")
        markdown = _render_markdown(report)

        assert "**Result:** ❌ FAIL" in markdown

    def test_render_verdict_section_warn(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(verdict="warn")
        markdown = _render_markdown(report)

        assert "**Result:** ⚠️ WARN" in markdown

    def test_render_attribution(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(attribution="stream")
        markdown = _render_markdown(report)

        assert "**Primary Attribution:** stream" in markdown

    def test_render_affected_ports(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(affected_ports=["eth0", "eth1"])
        markdown = _render_markdown(report)

        assert "**Affected Ports:** eth0, eth1" in markdown

    def test_render_fault_domain(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(fault_domain="Stream configuration")
        markdown = _render_markdown(report)

        assert "**Likely Fault Domain:** Stream configuration" in markdown

    def test_render_recommended_actions(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        assert "## Recommended Actions" in markdown
        assert "Check MTU consistency" in markdown

    def test_render_notes(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        assert "Test executed with nominal loss injection" in markdown


class TestSummaryReportGolden:
    def test_golden_summary_md_structure(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report(run_id="golden-md-001")
        markdown = _render_markdown(report)

        required_sections = [
            "# GVStress Run Report: golden-md-001",
            "## Scenario",
            "## Preflight",
            "## Collected Samples",
            "## Verdict",
            "## Recommended Actions",
        ]

        for section in required_sections:
            assert section in markdown, f"Missing section: {section}"

    def test_golden_summary_md_consistency_with_run_json(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)

        run_artifact = builder.build_run_artifact(
            run_id="consistent-001",
            verdict="fail",
            attribution="mixed",
        )

        summary = builder.build_summary_report(
            run_id="consistent-001",
            verdict="fail",
            attribution="mixed",
        )

        assert run_artifact.run_id == summary.run_id
        assert run_artifact.verdict == summary.verdict.verdict
        assert run_artifact.primary_attribution == summary.verdict.primary_attribution
        assert (
            run_artifact.secondary_attribution == summary.verdict.secondary_attribution
        )

    def test_golden_summary_md_contradiction_detection(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)

        run_artifact = builder.build_run_artifact(
            run_id="contradict-001",
            verdict="pass",
            attribution="nic",
        )

        summary_matching = builder.build_summary_report(
            run_id="contradict-001",
            verdict="pass",
            attribution="nic",
        )

        summary_mismatched = builder.build_summary_report(
            run_id="contradict-001",
            verdict="fail",
            attribution="stream",
        )

        assert run_artifact.run_id == summary_matching.run_id
        assert run_artifact.verdict == summary_matching.verdict.verdict
        assert (
            run_artifact.primary_attribution
            == summary_matching.verdict.primary_attribution
        )

        assert run_artifact.run_id == summary_mismatched.run_id
        assert run_artifact.verdict != summary_mismatched.verdict.verdict
        assert (
            run_artifact.primary_attribution
            != summary_mismatched.verdict.primary_attribution
        )

    def test_golden_summary_md_field_consistency(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)

        run_artifact = builder.build_run_artifact(run_id="fields-001")
        summary = builder.build_summary_report(run_id="fields-001")

        assert run_artifact.run_id == summary.run_id
        assert run_artifact.recommended_actions == summary.recommended_actions


class TestMarkdownRendererOutput:
    def test_output_is_valid_markdown(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        assert markdown.startswith("# ")
        assert len(markdown.splitlines()) > 10

    def test_no_empty_sections(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        report = builder.build_summary_report()
        markdown = _render_markdown(report)

        sections = re.split(r"\n## ", markdown)
        for section in sections[1:]:
            assert len(section.strip()) > 0, "Found empty section"

    def test_emoji_verdict_mapping(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)

        verdict_emoji_map = {
            "pass": "✅",
            "fail": "❌",
            "warn": "⚠️",
            "not_applicable": "➖",
        }

        for verdict, expected_emoji in verdict_emoji_map.items():
            report = builder.build_summary_report(verdict=verdict)
            markdown = _render_markdown(report)
            assert expected_emoji in markdown, f"Missing emoji for verdict: {verdict}"
