from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from gvstress.config.models import (
    DUTCollectOptions,
    DUTConfig,
    FakeCameraConfig,
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
from gvstress.core.preflight import PreflightCheck, PreflightResult
from gvstress.core.recommended_actions import recommended_actions_for
from gvstress.core.verdict import likely_fault_domain_for, secondary_attribution_for
from gvstress.dut.environment import EnvironmentSnapshot, InterfaceSnapshot
from gvstress.report.models import (
    PreflightSummary,
    RunArtifact,
    SamplesSummary,
    SummaryReport,
    VerdictSummary,
)


@dataclass(slots=True)
class FixtureBuilder:
    base_path: Path = Path("/tmp/artifacts/test-run-001")

    def build_environment_snapshot(
        self, hostname: str = "test-host", iface_count: int = 2
    ) -> EnvironmentSnapshot:
        interfaces = [
            InterfaceSnapshot(
                name=f"eth{i}",
                ip_addresses=[f"192.168.1.{10 + i}"],
                driver="mlx5_core",
                driver_version="5.0.0",
                firmware="20.0.0",
                mtu=9000,
                speed=25000,
                link_state="UP",
                link_up=True,
            )
            for i in range(iface_count)
        ]

        return EnvironmentSnapshot(
            hostname=hostname,
            platform="linux",
            python_version="3.11.0",
            interfaces=interfaces,
            required_binaries={
                "python3": True,
                "ip": True,
                "ethtool": True,
            },
            sudo_available=True,
            arv_fake_camera_present=True,
            pktgen_available=True,
            msix_detected=True,
            irqbalance_detected=True,
        )

    def build_preflight_result(
        self,
        validity: RunValidity = RunValidity.VALID,
        reasons: list[str] | None = None,
    ) -> PreflightResult:
        generator_env = self.build_environment_snapshot("generator-host")
        dut_env = self.build_environment_snapshot("dut-host")

        checks = [
            PreflightCheck(name="ssh", passed=True, reasons=[]),
            PreflightCheck(name="binaries", passed=True, reasons=[]),
            PreflightCheck(name="privileges", passed=True, reasons=[]),
            PreflightCheck(name="interfaces", passed=True, reasons=[]),
            PreflightCheck(name="link_state", passed=True, reasons=[]),
        ]

        return PreflightResult(
            run_validity=validity,
            reasons=reasons or [],
            checks=checks,
            generator_environment=generator_env,
            dut_environment=dut_env,
            generator_environment_path=self.base_path / "generator_environment.json",
            dut_environment_path=self.base_path / "dut_environment.json",
            preflight_path=self.base_path / "preflight.json",
        )

    def build_run_artifact(
        self,
        run_id: str = "test-run-001",
        validity: RunValidity | str = RunValidity.VALID,
        verdict: Verdict | str = Verdict.PASS,
        attribution: PrimaryAttribution | str = PrimaryAttribution.NIC,
        secondary_attribution: SecondaryAttribution | str | None = None,
    ) -> RunArtifact:
        validity_value = RunValidity(validity)
        verdict_value = Verdict(verdict)
        attribution_value = PrimaryAttribution(attribution)
        secondary_attribution_value = (
            SecondaryAttribution(secondary_attribution)
            if secondary_attribution is not None
            else secondary_attribution_for(attribution_value)
        )
        preflight = self.build_preflight_result(validity_value)

        samples: dict[Literal["nic", "stream", "system", "events"], Path] = {
            "nic": self.base_path / "raw" / "nic_samples.jsonl",
            "stream": self.base_path / "raw" / "stream_samples.jsonl",
            "system": self.base_path / "raw" / "system_samples.jsonl",
            "events": self.base_path / "raw" / "events_samples.jsonl",
        }

        return RunArtifact(
            run_id=run_id,
            run_validity=validity_value,
            scenario=ScenarioConfig(
                name=ScenarioType.FOUR_STREAM,
                duration=300,
                warmup=10,
                cooldown=5,
            ),
            fake_camera_config=FakeCameraConfig(
                ip_address="192.168.1.100",
                interface_name="eth0",
                serial_number="CAM001",
                genicam_filename="camera.xml",
                gvsp_lost_ratio=0.001,
            ),
            dut_config=DUTConfig(
                ifaces=["eth0", "eth1"],
                sample_interval_ms=100,
                collect=DUTCollectOptions(nic=True, stream=True, system=True),
            ),
            stream_config=StreamConfig(
                packet_resend=True,
                socket_buffer=True,
                socket_buffer_size=262144,
                frame_retention=30,
                initial_packet_timeout=500,
                packet_timeout=100,
                packet_request_ratio=0.1,
                receiver_priority=5,
            ),
            preflight=preflight,
            samples=samples,
            verdict=verdict_value,
            primary_attribution=attribution_value,
            secondary_attribution=secondary_attribution_value,
            recommended_actions=list(recommended_actions_for(attribution_value)),
            baseline_only=False,
            pktgen_baseline=None,
            compatible_baseline=None,
            run_config=None,
            notes="Test executed with nominal loss injection.",
        )

    def build_summary_report(
        self,
        run_id: str = "test-run-001",
        verdict: Verdict | str = Verdict.PASS,
        attribution: PrimaryAttribution | str = PrimaryAttribution.NIC,
        secondary_attribution: SecondaryAttribution | str | None = None,
        affected_ports: list[str] | None = None,
        fault_domain: str | None = None,
    ) -> SummaryReport:
        preflight = self.build_preflight_result()
        checks_passed = sum(1 for check in preflight.checks if check.passed)
        checks_failed = len(preflight.checks) - checks_passed
        verdict_value = Verdict(verdict)
        attribution_value = PrimaryAttribution(attribution)
        secondary_attribution_value = (
            SecondaryAttribution(secondary_attribution)
            if secondary_attribution is not None
            else secondary_attribution_for(attribution_value)
        )

        return SummaryReport(
            run_id=run_id,
            timestamp=datetime(2026, 4, 8, 10, 30, 0),
            scenario_name=ScenarioType.FOUR_STREAM,
            scenario_duration=300,
            preflight=PreflightSummary(
                run_validity=preflight.run_validity,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                generator_environment_path=str(preflight.generator_environment_path),
                dut_environment_path=str(preflight.dut_environment_path),
                preflight_path=str(preflight.preflight_path),
                reasons=preflight.reasons,
            ),
            samples=SamplesSummary(
                nic_samples=150,
                stream_samples=150,
                system_samples=150,
                events_samples=5,
                nic_path=str(self.base_path / "raw" / "nic_samples.jsonl"),
                stream_path=str(self.base_path / "raw" / "stream_samples.jsonl"),
                system_path=str(self.base_path / "raw" / "system_samples.jsonl"),
                events_path=str(self.base_path / "raw" / "events_samples.jsonl"),
            ),
            verdict=VerdictSummary(
                verdict=verdict_value,
                primary_attribution=attribution_value,
                secondary_attribution=secondary_attribution_value,
                affected_ports=affected_ports or ["eth0", "eth1"],
                likely_fault_domain=fault_domain
                or likely_fault_domain_for(secondary_attribution_value),
            ),
            recommended_actions=list(recommended_actions_for(attribution_value)),
            notes="Test executed with nominal loss injection.",
        )
