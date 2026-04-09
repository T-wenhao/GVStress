from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class RunValidity(str, Enum):
    VALID = "valid"
    INVALID_ENVIRONMENT = "invalid_environment"
    INVALID_PREREQ = "invalid_prereq"
    INVALID_MAPPING = "invalid_mapping"
    INVALID_TELEMETRY = "invalid_telemetry"
    INTERRUPTED = "interrupted"


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class PrimaryAttribution(str, Enum):
    NIC = "nic"
    STREAM = "stream"
    MIXED = "mixed"
    ENVIRONMENT = "environment"
    UNKNOWN = "unknown"


class SecondaryAttribution(str, Enum):
    UNKNOWN = "unknown"
    ENVIRONMENT = "environment"
    SCENARIO_ORCHESTRATION = "scenario_orchestration"
    PKTGEN_BASELINE = "pktgen_baseline"
    NIC_DRIVER_CONFIGURATION = "nic_driver_configuration"
    STREAM_CONFIGURATION = "stream_configuration"


class ScenarioType(str, Enum):
    SMOKE = "smoke"
    FOUR_STREAM = "four_stream"
    SOAK = "soak"
    LOSS_INJECTION = "loss_injection"
    PKTGEN_BASELINE = "pktgen_baseline"


class RunArtifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str
    path: Path


class RunArtifacts(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    root: Path
    raw_dir: Path
    reports_dir: Path
    logs_dir: Path
    evidence_dir: Path
    run_json: Path
    summary_md: Path
