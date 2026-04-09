from __future__ import annotations

from pathlib import Path

import pytest

from gvstress.core.models import Verdict
from gvstress.report.models import (
    CompatibleBaselineReference,
    IRQContextSummary,
    PktgenBaselineSummary,
    PktgenInterfaceSummary,
)
from gvstress.report.renderer import MarkdownRenderer, render_summary_to_markdown
from tests.fixtures.reports.helpers import FixtureBuilder


@pytest.mark.parametrize(
    ("verdict", "emoji"),
    [
        (Verdict.PASS, "✅ PASS"),
        (Verdict.WARN, "⚠️ WARN"),
        (Verdict.FAIL, "❌ FAIL"),
        (Verdict.NOT_APPLICABLE, "➖ NOT_APPLICABLE"),
    ],
)
def test_markdown_renderer_renders_all_verdict_emojis(
    tmp_path: Path, verdict: Verdict, emoji: str
) -> None:
    report = (
        FixtureBuilder(tmp_path)
        .build_summary_report(verdict=verdict)
        .model_copy(update={"recommended_actions": [], "notes": None})
    )

    rendered = MarkdownRenderer().render(report)

    assert f"**Result:** {emoji}" in rendered
    assert "No specific actions recommended." in rendered


def test_markdown_renderer_renders_optional_sections_for_scenario_report(
    tmp_path: Path,
) -> None:
    report = (
        FixtureBuilder(tmp_path)
        .build_summary_report()
        .model_copy(
            update={
                "preflight": FixtureBuilder(tmp_path)
                .build_summary_report()
                .preflight.model_copy(update={"reasons": ["missing irq affinity"]}),
                "compatible_baseline": CompatibleBaselineReference(
                    run_id="baseline-001",
                    interface_names=["eth0", "eth1"],
                    packet_size=1500,
                    duration_seconds=300,
                    per_interface_mbps={"eth1": 950, "eth0": 900},
                ),
            }
        )
    )

    rendered = MarkdownRenderer().render(report)

    assert "**Issues:**" in rendered
    assert "- missing irq affinity" in rendered
    assert "## Baseline Comparison" in rendered
    assert "- **Baseline Run ID:** baseline-001" in rendered
    assert "- **eth0 Baseline Throughput:** 900 Mb/s" in rendered
    assert "- **Affected Ports:** eth0, eth1" in rendered
    assert "## Notes" in rendered


def test_render_summary_to_markdown_supports_baseline_only_reports(
    tmp_path: Path,
) -> None:
    report = (
        FixtureBuilder(tmp_path)
        .build_summary_report()
        .model_copy(
            update={
                "baseline_only": True,
                "pktgen_baseline": PktgenBaselineSummary(
                    interfaces=[
                        PktgenInterfaceSummary(
                            interface="eth0",
                            device_name="pktgen0",
                            thread_name="kpktgend_0",
                            packets=100,
                            packet_size=1500,
                            errors=0,
                            duration_usec=1000,
                            pps=10,
                            mbps=20,
                            bps=20000000,
                            rate="20M",
                            ratep=None,
                            xmit_mode="start_xmit",
                            result="ok",
                            source_path="/tmp/pktgen.json",
                        )
                    ],
                    irq_context=[
                        IRQContextSummary(
                            interface="eth0",
                            dominant_cpu="cpu0",
                            irq_descriptions=["test irq"],
                            total_counts={"100": 10},
                            delta_counts={"100": 2},
                        )
                    ],
                ),
                "notes": None,
            }
        )
    )
    output_path = tmp_path / "reports" / "summary.md"

    returned = render_summary_to_markdown(report, output_path)
    rendered = output_path.read_text(encoding="utf-8")

    assert returned is report
    assert "## Pktgen Baseline" in rendered
    assert "**CPU/IRQ Context:**" in rendered
    assert "## Verdict" not in rendered
