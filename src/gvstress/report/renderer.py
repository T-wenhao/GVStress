# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path

from gvstress.report.models import SummaryReport


class MarkdownRenderer:
    def render(self, report: SummaryReport) -> str:
        lines: list[str] = []

        lines.append(f"# GVStress Run Report: {report.run_id}")
        lines.append("")
        lines.append(f"**Timestamp:** {report.timestamp.isoformat()}")
        lines.append(f"**Schema Version:** {report.schema_version}")
        lines.append("")

        lines.append("## Scenario")
        lines.append("")
        lines.append(f"- **Type:** {report.scenario_name.value}")
        lines.append(f"- **Duration:** {report.scenario_duration}s")
        lines.append("")

        lines.append("## Preflight")
        lines.append("")
        lines.append(f"- **Validity:** {report.preflight.run_validity.value}")
        lines.append(f"- **Checks Passed:** {report.preflight.checks_passed}")
        lines.append(f"- **Checks Failed:** {report.preflight.checks_failed}")
        if report.preflight.reasons:
            lines.append("")
            lines.append("**Issues:**")
            for reason in report.preflight.reasons:
                lines.append(f"- {reason}")
        lines.append("")

        lines.append("## Collected Samples")
        lines.append("")
        lines.append(f"- **NIC Samples:** {report.samples.nic_samples}")
        lines.append(f"- **Stream Samples:** {report.samples.stream_samples}")
        lines.append(f"- **System Samples:** {report.samples.system_samples}")
        lines.append(f"- **Event Samples:** {report.samples.events_samples}")
        lines.append("")

        if report.baseline_only and report.pktgen_baseline is not None:
            lines.append("## Pktgen Baseline")
            lines.append("")
            for interface in report.pktgen_baseline.interfaces:
                lines.append(
                    f"- **{interface.interface}** ({interface.thread_name}): "
                    f"{interface.mbps or 0} Mb/s, {interface.pps or 0} pps, "
                    f"errors={interface.errors or 0}"
                )
            if report.pktgen_baseline.irq_context:
                lines.append("")
                lines.append("**CPU/IRQ Context:**")
                for irq_context in report.pktgen_baseline.irq_context:
                    lines.append(
                        f"- {irq_context.interface}: dominant_cpu={irq_context.dominant_cpu or 'unknown'}"
                    )
            lines.append("")

        if not report.baseline_only and report.compatible_baseline is not None:
            lines.append("## Baseline Comparison")
            lines.append("")
            lines.append(f"- **Baseline Run ID:** {report.compatible_baseline.run_id}")
            lines.append(
                "- **Interfaces:** "
                + ", ".join(report.compatible_baseline.interface_names)
            )
            for iface_name, mbps in sorted(
                report.compatible_baseline.per_interface_mbps.items()
            ):
                lines.append(f"- **{iface_name} Baseline Throughput:** {mbps} Mb/s")
            lines.append("")

        if not report.baseline_only:
            lines.append("## Verdict")
            lines.append("")
            verdict_emoji = {
                "pass": "✅",
                "warn": "⚠️",
                "fail": "❌",
                "not_applicable": "➖",
            }
            emoji = verdict_emoji.get(report.verdict.verdict.value, "")
            lines.append(f"**Result:** {emoji} {report.verdict.verdict.value.upper()}")
            lines.append("")
            lines.append(
                f"- **Primary Attribution:** {report.verdict.primary_attribution.value}"
            )
            lines.append(
                f"- **Secondary Attribution:** {report.verdict.secondary_attribution.value}"
            )
            if report.verdict.affected_ports:
                lines.append(
                    f"- **Affected Ports:** {', '.join(report.verdict.affected_ports)}"
                )
            lines.append(
                f"- **Likely Fault Domain:** {report.verdict.likely_fault_domain}"
            )
            lines.append("")

            lines.append("## Recommended Actions")
            lines.append("")
            if report.recommended_actions:
                for action in report.recommended_actions:
                    lines.append(f"- {action}")
            else:
                lines.append("No specific actions recommended.")
            lines.append("")

        if report.notes:
            lines.append("## Notes")
            lines.append("")
            lines.append(report.notes)
            lines.append("")

        return "\n".join(lines)


def render_summary_to_markdown(
    report: SummaryReport, output_path: Path
) -> SummaryReport:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(MarkdownRenderer().render(report), encoding="utf-8")
    return report
