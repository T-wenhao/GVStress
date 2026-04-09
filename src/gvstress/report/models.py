# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from gvstress.config.models import (
    Config as RunConfig,
)
from gvstress.config.models import (
    DUTConfig,
    FakeCameraConfig,
    ScenarioConfig,
    StreamConfig,
)
from gvstress.core import models as core_models

PrimaryAttribution = core_models.PrimaryAttribution
RunValidity = core_models.RunValidity
ScenarioType = core_models.ScenarioType
SecondaryAttribution = core_models.SecondaryAttribution
Verdict = core_models.Verdict

if TYPE_CHECKING:
    pass

RUNTIME_PREFLIGHT_TYPE = object


SCHEMA_VERSION: str = "1.0.0"


class RunArtifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default=SCHEMA_VERSION, description="Schema version for versioned support"
    )
    run_id: str = Field(..., description="Unique run identifier")
    run_validity: RunValidity = Field(..., description="Overall run validity state")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Run completion timestamp",
    )

    scenario: ScenarioConfig = Field(..., description="Scenario that was executed")
    fake_camera_config: FakeCameraConfig = Field(
        ..., description="Fake camera configuration"
    )
    dut_config: DUTConfig = Field(..., description="DUT configuration")
    stream_config: StreamConfig = Field(..., description="Stream configuration")

    preflight: RUNTIME_PREFLIGHT_TYPE = Field(
        ..., description="Preflight check results"
    )

    samples: dict[Literal["nic", "stream", "system", "events"], Path] = Field(
        default_factory=dict,
        description="Paths to JSON Lines files with raw samples keyed by source",
    )

    verdict: Verdict = Field(
        ..., description="Test verdict: pass, warn, fail, or not_applicable"
    )
    primary_attribution: PrimaryAttribution = Field(
        ..., description="Primary fault domain attribution"
    )
    secondary_attribution: SecondaryAttribution = Field(
        ..., description="Secondary fault domain attribution"
    )

    recommended_actions: list[str] = Field(
        default_factory=list, description="List of recommended tuning actions"
    )
    baseline_only: bool = Field(
        False, description="True when artifact is baseline-only"
    )
    pktgen_baseline: PktgenBaselineSummary | None = Field(
        None,
        description="Pktgen baseline details when present",
    )
    compatible_baseline: CompatibleBaselineReference | None = Field(
        None,
        description="Compatible baseline context for later scenario reports",
    )

    run_config: RunConfig | None = Field(
        None, description="Full run configuration if available"
    )
    notes: str | None = Field(None, description="Optional notes or comments")


class PreflightSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    run_validity: RunValidity
    checks_passed: int
    checks_failed: int
    generator_environment_path: str | None
    dut_environment_path: str | None
    preflight_path: str | None
    reasons: list[str]


class SamplesSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    nic_samples: int = Field(default=0, description="Number of NIC samples collected")
    stream_samples: int = Field(
        default=0, description="Number of stream samples collected"
    )
    system_samples: int = Field(
        default=0, description="Number of system samples collected"
    )
    events_samples: int = Field(
        default=0, description="Number of event samples collected"
    )
    nic_path: str | None = None
    stream_path: str | None = None
    system_path: str | None = None
    events_path: str | None = None


class VerdictSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    verdict: Verdict
    primary_attribution: PrimaryAttribution
    secondary_attribution: SecondaryAttribution
    affected_ports: list[str] = Field(default_factory=list)
    likely_fault_domain: str = Field(
        ..., description="Human-readable fault domain description"
    )


class PktgenInterfaceSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    interface: str
    device_name: str
    thread_name: str
    packets: int | None = None
    packet_size: int | None = None
    errors: int | None = None
    duration_usec: int | None = None
    pps: int | None = None
    mbps: int | None = None
    bps: int | None = None
    rate: str | None = None
    ratep: int | None = None
    xmit_mode: str | None = None
    result: str
    source_path: str


class IRQContextSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    interface: str
    dominant_cpu: str | None = None
    irq_descriptions: list[str] = Field(default_factory=list)
    total_counts: dict[str, int] = Field(default_factory=dict)
    delta_counts: dict[str, int] = Field(default_factory=dict)


class CPUContextSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    cpu: str
    usage_pct: float | None = None


class PktgenBaselineSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    interfaces: list[PktgenInterfaceSummary] = Field(default_factory=list)
    control_script_paths: list[str] = Field(default_factory=list)
    nic_sample_count: int = 0
    system_sample_count: int = 0
    irq_context: list[IRQContextSummary] = Field(default_factory=list)
    cpu_context: list[CPUContextSummary] = Field(default_factory=list)


class CompatibleBaselineReference(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    run_id: str
    interface_names: list[str] = Field(default_factory=list)
    packet_size: int | None = None
    duration_seconds: int | None = None
    per_interface_mbps: dict[str, int] = Field(default_factory=dict)


class SummaryReport(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, description="Schema version")
    run_id: str
    timestamp: datetime
    scenario_name: ScenarioType
    scenario_duration: int
    preflight: PreflightSummary
    samples: SamplesSummary
    verdict: VerdictSummary
    recommended_actions: list[str]
    baseline_only: bool = False
    pktgen_baseline: PktgenBaselineSummary | None = None
    compatible_baseline: CompatibleBaselineReference | None = None
    notes: str | None = None
