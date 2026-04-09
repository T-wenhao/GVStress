# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from __future__ import annotations

import json
from pathlib import Path

from gvstress.baseline.pktgen_runner import PktgenRunner
from gvstress.cli.baseline import (
    attach_compatible_baseline_to_report,
    run_pktgen_baseline,
)
from gvstress.config.models import (
    Config,
    DUTCollectOptions,
    DUTConfig,
    FakeCameraConfig,
    GeneratorConfig,
    OutputConfig,
    PktgenConfig,
    ScenarioConfig,
    StreamConfig,
)
from gvstress.core.models import (
    PrimaryAttribution,
    RunValidity,
    ScenarioType,
    SecondaryAttribution,
    Verdict,
)
from gvstress.dut.environment import EnvironmentSnapshot, InterfaceSnapshot
from gvstress.report.models import (
    PreflightSummary,
    RunArtifact,
    SamplesSummary,
    SummaryReport,
    VerdictSummary,
)
from gvstress.report.renderer import render_summary_to_markdown
from gvstress.report.writer import JSONWriter


class ManualClock:
    def __init__(self) -> None:
        self.current = 0.0

    def __call__(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += seconds


class FakeProbe:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self._payloads = payloads
        self._index = 0

    def collect(self) -> dict[str, object]:
        payload = self._payloads[min(self._index, len(self._payloads) - 1)]
        self._index += 1
        return payload


class FakePktgenRunner(PktgenRunner):
    def __init__(
        self, config: PktgenConfig, *, proc_root: Path, sample_output: str
    ) -> None:
        super().__init__(config, proc_root=proc_root)
        self.sample_output = sample_output

    def stop(self) -> None:
        super().stop()
        for assignment in self.build_assignments():
            assignment.source_path.write_text(self.sample_output, encoding="utf-8")


def test_baseline_report_is_marked_baseline_only(tmp_path: Path, monkeypatch) -> None:
    proc_root = tmp_path / "proc" / "net" / "pktgen"
    proc_root.mkdir(parents=True)
    for name in ["kpktgend_0", "kpktgend_1", "eno1@0", "eno2@1", "pgctrl"]:
        (proc_root / name).write_text("", encoding="utf-8")

    config = _build_config(tmp_path)
    environment = _build_environment_snapshot()
    monkeypatch.setattr(
        "gvstress.cli.baseline.collect_local_environment_snapshot",
        lambda ifaces: environment,
    )
    clock = ManualClock()
    pktgen_runner = FakePktgenRunner(
        config.pktgen,
        proc_root=proc_root,
        sample_output="""Params:
 count 0  pkt_size 1500  xmit_mode start_xmit rate 1000M
Current:
 pkts-sofar: 100000  errors: 0
Result: OK: 15430(c15405+d25) usec, 100000 (1500byte,0frags)
6480562pps 3110Mb/sec (3110669760bps) errors: 0
""",
    )
    nic_probe = FakeProbe(
        [
            {"interfaces": {"eno1": {"tx_bytes": 100}, "eno2": {"tx_bytes": 200}}},
            {"interfaces": {"eno1": {"tx_bytes": 110}, "eno2": {"tx_bytes": 220}}},
        ]
    )
    system_probe = FakeProbe(
        [
            {
                "cpus": {"cpu0": {"usage_pct": 55.5}, "cpu1": {"usage_pct": 44.5}},
                "interfaces": {
                    "eno1": {
                        "dominant_cpu": "CPU0",
                        "irqs": [{"description": "eno1-TxRx-0"}],
                        "total_counts": {"CPU0": 100},
                        "delta_counts": {"CPU0": 10},
                    },
                    "eno2": {
                        "dominant_cpu": "CPU1",
                        "irqs": [{"description": "eno2-TxRx-0"}],
                        "total_counts": {"CPU1": 120},
                        "delta_counts": {"CPU1": 12},
                    },
                },
            }
        ]
    )

    payload = run_pktgen_baseline(
        config,
        output_root=tmp_path / "baseline-output",
        proc_root=proc_root,
        clock=clock,
        sleep=clock.sleep,
        run_id_factory=lambda: "baseline-001",
        pktgen_runner=pktgen_runner,
        nic_probe=nic_probe,
        system_probe=system_probe,
    )

    assert payload["baseline_only"] is True
    run_json = json.loads(
        (
            tmp_path / "baseline-output" / "baseline-001" / "reports" / "run.json"
        ).read_text(encoding="utf-8")
    )
    assert run_json["baseline_only"] is True
    assert run_json["pktgen_baseline"]["interfaces"][0]["mbps"] == 3110
    assert run_json["pktgen_baseline"]["nic_sample_count"] == 3
    assert run_json["pktgen_baseline"]["system_sample_count"] == 3
    assert run_json["pktgen_baseline"]["irq_context"][0]["dominant_cpu"] == "CPU0"
    assert Path(payload["control_scripts"][0]).exists()

    summary_md = (
        tmp_path / "baseline-output" / "baseline-001" / "reports" / "summary.md"
    ).read_text(encoding="utf-8")
    assert "## Pktgen Baseline" in summary_md
    assert "## Verdict" not in summary_md


def test_scenario_report_references_latest_compatible_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    test_baseline_report_is_marked_baseline_only(tmp_path, monkeypatch)

    scenario_root = tmp_path / "scenario-output" / "run-001"
    reports_dir = scenario_root / "reports"
    raw_dir = scenario_root / "raw"
    reports_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    for name in [
        "nic_samples.jsonl",
        "stream_samples.jsonl",
        "system_samples.jsonl",
        "events_samples.jsonl",
    ]:
        (raw_dir / name).write_text("{}\n", encoding="utf-8")

    artifact = RunArtifact(
        run_id="run-001",
        run_validity=RunValidity.VALID,
        scenario=ScenarioConfig(
            name=ScenarioType.SMOKE, duration=60, warmup=10, cooldown=5
        ),
        fake_camera_config=FakeCameraConfig(
            ip_address="192.168.10.11",
            interface_name="eno1",
            serial_number="CAM-001",
            genicam_filename="camera.xml",
            gvsp_lost_ratio=0.0,
        ),
        dut_config=_build_config(tmp_path).dut,
        stream_config=_build_config(tmp_path).stream,
        preflight={"checks": [], "reasons": []},
        samples={
            "nic": raw_dir / "nic_samples.jsonl",
            "stream": raw_dir / "stream_samples.jsonl",
            "system": raw_dir / "system_samples.jsonl",
            "events": raw_dir / "events_samples.jsonl",
        },
        verdict=Verdict.PASS,
        primary_attribution=PrimaryAttribution.UNKNOWN,
        secondary_attribution=SecondaryAttribution.SCENARIO_ORCHESTRATION,
        recommended_actions=[],
        baseline_only=False,
        pktgen_baseline=None,
        compatible_baseline=None,
        run_config=None,
        notes=None,
    )
    JSONWriter().write(artifact, reports_dir / "run.json")
    render_summary_to_markdown(
        SummaryReport(
            run_id="run-001",
            timestamp=artifact.timestamp,
            scenario_name=ScenarioType.SMOKE,
            scenario_duration=60,
            preflight=PreflightSummary(
                run_validity=RunValidity.VALID,
                checks_passed=0,
                checks_failed=0,
                generator_environment_path=None,
                dut_environment_path=None,
                preflight_path=None,
                reasons=[],
            ),
            samples=SamplesSummary(
                nic_samples=1,
                stream_samples=1,
                system_samples=1,
                events_samples=1,
                nic_path=str(raw_dir / "nic_samples.jsonl"),
                stream_path=str(raw_dir / "stream_samples.jsonl"),
                system_path=str(raw_dir / "system_samples.jsonl"),
                events_path=str(raw_dir / "events_samples.jsonl"),
            ),
            verdict=VerdictSummary(
                verdict=Verdict.PASS,
                primary_attribution=PrimaryAttribution.UNKNOWN,
                secondary_attribution=SecondaryAttribution.SCENARIO_ORCHESTRATION,
                affected_ports=["eno1", "eno2"],
                likely_fault_domain="Scenario orchestration",
            ),
            recommended_actions=[],
        ),
        reports_dir / "summary.md",
    )

    baseline_ref = attach_compatible_baseline_to_report(
        scenario_root,
        search_root=tmp_path,
        interface_names=["eno1", "eno2"],
        exclude_run_id="run-001",
    )

    assert baseline_ref is not None
    run_json = json.loads((reports_dir / "run.json").read_text(encoding="utf-8"))
    assert run_json["compatible_baseline"]["run_id"] == "baseline-001"
    summary_md = (reports_dir / "summary.md").read_text(encoding="utf-8")
    assert "## Baseline Comparison" in summary_md
    assert "baseline-001" in summary_md


def _build_environment_snapshot() -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        hostname="generator",
        platform="linux",
        python_version="3.11.0",
        interfaces=[
            InterfaceSnapshot(
                name="eno1",
                ip_addresses=["192.168.10.11"],
                driver="igb",
                driver_version="1.0",
                firmware="1.0",
                mtu=1500,
                speed=1000,
                link_state="UP",
                link_up=True,
            ),
            InterfaceSnapshot(
                name="eno2",
                ip_addresses=["192.168.10.12"],
                driver="igb",
                driver_version="1.0",
                firmware="1.0",
                mtu=1500,
                speed=1000,
                link_state="UP",
                link_up=True,
            ),
        ],
        required_binaries={"python3": True, "ip": True, "ethtool": True},
        sudo_available=True,
        arv_fake_camera_present=True,
        pktgen_available=True,
        msix_detected=True,
        irqbalance_detected=True,
    )


def _build_config(tmp_path: Path) -> Config:
    return Config(
        generator=GeneratorConfig(
            cameras=[
                FakeCameraConfig(
                    ip_address="192.168.10.11",
                    interface_name="eno1",
                    serial_number="CAM-001",
                    genicam_filename="camera.xml",
                    gvsp_lost_ratio=0.0,
                )
            ]
        ),
        dut=DUTConfig(
            ifaces=["eno1", "eno2"],
            sample_interval_ms=1000,
            collect=DUTCollectOptions(nic=True, stream=False, system=True),
        ),
        stream=StreamConfig(
            packet_resend=True,
            socket_buffer=True,
            socket_buffer_size=262144,
            frame_retention=30,
            initial_packet_timeout=500,
            packet_timeout=100,
            packet_request_ratio=0.1,
            receiver_priority=5,
        ),
        scenarios=[
            ScenarioConfig(name=ScenarioType.SMOKE, duration=60, warmup=10, cooldown=5)
        ],
        pktgen=PktgenConfig(
            interfaces=["eno1", "eno2"],
            duration=2,
            packet_size=1500,
            rate="1000M",
            xmit_mode="start_xmit",
        ),
        output=OutputConfig(
            root=tmp_path / "artifacts",
            raw_dir=tmp_path / "artifacts" / "raw",
            reports_dir=tmp_path / "artifacts" / "reports",
            logs_dir=tmp_path / "artifacts" / "logs",
            evidence_dir=tmp_path / "artifacts" / "evidence",
        ),
    )
